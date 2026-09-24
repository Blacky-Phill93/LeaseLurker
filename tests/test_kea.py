from __future__ import annotations

import httpx
import pytest

from lease_lurker.kea import KeaError, KeaProvider, normalize_mac
from lease_lurker.settings import KeaSettings


def client_for(payload: object, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload, request=request)

    return httpx.AsyncClient(
        base_url="http://kea.test/", transport=httpx.MockTransport(handler)
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00-11-22-33-44-55", "00:11:22:33:44:55"),
        ("0011.2233.4455", "00:11:22:33:44:55"),
        ("001122334455", "00:11:22:33:44:55"),
    ],
)
def test_normalize_mac(value: str, expected: str) -> None:
    assert normalize_mac(value) == expected


def test_normalize_mac_rejects_invalid_value() -> None:
    with pytest.raises(ValueError):
        normalize_mac("nope")


async def test_parses_subnets_and_leases(now) -> None:
    responses = iter(
        [
            [
                {
                    "result": 0,
                    "arguments": ["lease4-get-all", "subnet4-list", "config-get"],
                }
            ],
            [
                {
                    "result": 0,
                    "arguments": {
                        "subnets": [
                            {
                                "id": 1,
                                "subnet": "192.0.2.0/24",
                                "shared-network-name": "Office",
                            }
                        ]
                    },
                }
            ],
            [
                {
                    "result": 0,
                    "arguments": {
                        "leases": [
                            {
                                "ip-address": "192.0.2.41",
                                "hostname": "",
                                "hw-address": "",
                                "subnet-id": 1,
                                "cltt": int(now.timestamp()),
                                "valid-lft": 3600,
                                "state": 1,
                            },
                            {
                                "ip-address": "192.0.2.42",
                                "hostname": "pc.example.",
                                "hw-address": "00-11-22-33-44-55",
                                "subnet-id": 1,
                                "cltt": int(now.timestamp()),
                                "valid-lft": 3600,
                                "state": 0,
                            },
                            {
                                "ip-address": "192.0.2.43",
                                "hostname": "client-id-only.example.",
                                "hw-address": "",
                                "subnet-id": 1,
                                "cltt": int(now.timestamp()),
                                "valid-lft": 3600,
                                "state": 0,
                            },
                            {
                                "ip-address": "192.0.2.44",
                                "hostname": "invalid-mac.example.",
                                "hw-address": "not-a-mac",
                                "subnet-id": 1,
                                "cltt": int(now.timestamp()),
                                "valid-lft": 3600,
                                "state": 0,
                            },
                        ]
                    },
                }
            ],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses), request=request)

    client = httpx.AsyncClient(
        base_url="http://kea.test/", transport=httpx.MockTransport(handler)
    )
    provider = KeaProvider(KeaSettings(url="http://kea.test/"), client)
    subnets = await provider.get_subnets()
    leases = await provider.get_leases([1])
    assert len(leases) == 2
    assert subnets[0].name == "Office"
    assert leases[0].hostname == "pc.example"
    assert leases[0].mac_address == "00:11:22:33:44:55"
    assert leases[1].hostname == "client-id-only.example"
    assert leases[1].mac_address is None
    assert await provider.get_leases([]) == []


async def test_capability_check_reports_missing_command() -> None:
    provider = KeaProvider(
        KeaSettings(url="http://kea.test/"),
        client_for([{"result": 0, "arguments": {"commands": ["subnet4-list"]}}]),
    )
    with pytest.raises(KeaError, match="lease4-get-all"):
        await provider.check_capabilities()


async def test_capability_check_accepts_native_list_shape() -> None:
    provider = KeaProvider(
        KeaSettings(url="http://kea.test/"),
        client_for([{"result": 0, "arguments": ["lease4-get-all", "subnet4-list"]}]),
    )
    await provider.check_capabilities()


async def test_config_get_fallback_parses_direct_and_shared_subnets() -> None:
    responses = iter(
        [
            [
                {
                    "result": 0,
                    "arguments": ["lease4-get-all", "config-get"],
                }
            ],
            [
                {
                    "result": 0,
                    "arguments": {
                        "Dhcp4": {
                            "subnet4": [{"id": 2, "subnet": "198.51.100.0/24"}],
                            "shared-networks": [
                                {
                                    "name": "Campus",
                                    "subnet4": [{"id": 1, "subnet": "192.0.2.0/24"}],
                                }
                            ],
                        }
                    },
                }
            ],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses), request=request)

    client = httpx.AsyncClient(
        base_url="http://kea.test/", transport=httpx.MockTransport(handler)
    )
    provider = KeaProvider(KeaSettings(url="http://kea.test/"), client)
    subnets = await provider.get_subnets()
    assert [(item.id, item.prefix, item.name) for item in subnets] == [
        (2, "198.51.100.0/24", "198.51.100.0/24"),
        (1, "192.0.2.0/24", "Campus"),
    ]


async def test_capability_check_requires_a_subnet_source() -> None:
    provider = KeaProvider(
        KeaSettings(url="http://kea.test/"),
        client_for([{"result": 0, "arguments": ["lease4-get-all"]}]),
    )
    with pytest.raises(KeaError, match="subnet4-list or config-get"):
        await provider.check_capabilities()


@pytest.mark.parametrize(
    "dhcp4",
    [
        {"subnet4": "invalid"},
        {"shared-networks": "invalid"},
        {"shared-networks": [{"name": "", "subnet4": []}]},
        {"subnet4": [{"id": 1, "subnet": "192.0.2.0/24"}] * 2},
    ],
)
async def test_config_get_rejects_invalid_subnets(dhcp4: object) -> None:
    responses = iter(
        [
            [
                {
                    "result": 0,
                    "arguments": ["lease4-get-all", "config-get"],
                }
            ],
            [{"result": 0, "arguments": {"Dhcp4": dhcp4}}],
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses), request=request)

    provider = KeaProvider(
        KeaSettings(url="http://kea.test/"),
        httpx.AsyncClient(
            base_url="http://kea.test/", transport=httpx.MockTransport(handler)
        ),
    )
    with pytest.raises(KeaError):
        await provider.get_subnets()


@pytest.mark.parametrize(
    "payload",
    [
        {"not": "a list"},
        [],
        ["invalid"],
        [{"result": 1, "text": "denied"}],
    ],
)
async def test_protocol_errors(payload: object) -> None:
    provider = KeaProvider(KeaSettings(url="http://kea.test/"), client_for(payload))
    with pytest.raises(KeaError):
        await provider.get_subnets()


async def test_transport_error_and_reachability() -> None:
    provider = KeaProvider(
        KeaSettings(url="http://kea.test/"), client_for({"error": True}, 500)
    )
    assert await provider.is_reachable() is False


async def test_command_allowlist() -> None:
    provider = KeaProvider(KeaSettings(url="http://kea.test/"), client_for([]))
    with pytest.raises(KeaError, match="allowlisted"):
        await provider._command("lease4-del")  # type: ignore[attr-defined]
