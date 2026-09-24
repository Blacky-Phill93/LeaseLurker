"""Read-only Kea Control Agent adapter."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from lease_lurker.models import Lease, Subnet
from lease_lurker.settings import KeaSettings

LOGGER = logging.getLogger(__name__)


class KeaError(RuntimeError):
    """Raised for transport, protocol, or capability failures."""


class KeaProvider:
    """Kea adapter whose command allowlist contains only read operations."""

    REQUIRED_COMMANDS = frozenset({"lease4-get-all"})
    SUBNET_COMMANDS = ("subnet4-list", "config-get")
    ALLOWED_COMMANDS = (
        REQUIRED_COMMANDS
        | set(SUBNET_COMMANDS)
        | {
            "list-commands",
            "status-get",
        }
    )

    def __init__(
        self, settings: KeaSettings, client: httpx.AsyncClient | None = None
    ) -> None:
        auth = None
        if settings.username and settings.password:
            auth = (settings.username, settings.password.get_secret_value())
        self._owns_client = client is None
        self._subnet_command: str | None = None
        self._client = client or httpx.AsyncClient(
            base_url=str(settings.url),
            auth=auth,
            timeout=settings.timeout_seconds,
        )

    async def _command(
        self, command: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if command not in self.ALLOWED_COMMANDS:
            raise KeaError(f"Kea command is not read-only allowlisted: {command}")
        payload: dict[str, Any] = {"command": command, "service": ["dhcp4"]}
        if arguments is not None:
            payload["arguments"] = arguments
        try:
            response = await self._client.post("", json=payload)
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KeaError("Kea Control Agent request failed") from exc
        if not isinstance(document, list) or len(document) != 1:
            raise KeaError("Kea returned an unexpected response envelope")
        result = document[0]
        if not isinstance(result, dict):
            raise KeaError("Kea returned an invalid response object")
        code = result.get("result")
        if code not in {0, 3}:
            text = str(result.get("text", "unknown Kea error"))
            raise KeaError(f"Kea command {command} failed: {text}")
        return result

    async def check_capabilities(self) -> None:
        result = await self._command("list-commands")
        arguments = result.get("arguments", {})
        if isinstance(arguments, list):
            commands = arguments
        elif isinstance(arguments, dict):
            commands = arguments.get("commands", [])
        else:
            commands = []
        available = {str(item) for item in commands}
        missing = self.REQUIRED_COMMANDS - available
        if missing:
            raise KeaError(
                f"Kea is missing required commands: {', '.join(sorted(missing))}"
            )
        self._subnet_command = next(
            (command for command in self.SUBNET_COMMANDS if command in available),
            None,
        )
        if self._subnet_command is None:
            raise KeaError(
                "Kea is missing a subnet read command: subnet4-list or config-get"
            )
        LOGGER.info("Using Kea subnet source %s", self._subnet_command)

    async def get_subnets(self) -> list[Subnet]:
        if self._subnet_command is None:
            await self.check_capabilities()
        if self._subnet_command == "config-get":
            return await self._get_subnets_from_config()

        result = await self._command("subnet4-list")
        arguments = result.get("arguments", {})
        items = arguments.get("subnets", []) if isinstance(arguments, dict) else []
        return self._parse_subnets(items)

    async def _get_subnets_from_config(self) -> list[Subnet]:
        result = await self._command("config-get")
        arguments = result.get("arguments")
        if not isinstance(arguments, dict):
            raise KeaError("Kea configuration response is invalid")
        dhcp4 = arguments.get("Dhcp4")
        if not isinstance(dhcp4, dict):
            raise KeaError("Kea configuration has no valid Dhcp4 section")

        items: list[object] = []
        direct_subnets = dhcp4.get("subnet4", [])
        if not isinstance(direct_subnets, list):
            raise KeaError("Kea Dhcp4 subnet4 configuration is invalid")
        items.extend(direct_subnets)

        shared_networks = dhcp4.get("shared-networks", [])
        if not isinstance(shared_networks, list):
            raise KeaError("Kea Dhcp4 shared-networks configuration is invalid")
        for network in shared_networks:
            if not isinstance(network, dict):
                raise KeaError("Kea shared network entry is invalid")
            name = network.get("name")
            network_subnets = network.get("subnet4", [])
            if not isinstance(name, str) or not name.strip():
                raise KeaError("Kea shared network name is invalid")
            if not isinstance(network_subnets, list):
                raise KeaError("Kea shared network subnet4 configuration is invalid")
            for subnet in network_subnets:
                if not isinstance(subnet, dict):
                    raise KeaError("Kea subnet entry is invalid")
                items.append({**subnet, "shared-network-name": name})

        return self._parse_subnets(items)

    @staticmethod
    def _parse_subnets(items: object) -> list[Subnet]:
        if not isinstance(items, list):
            raise KeaError("Kea subnet list is invalid")
        subnets: list[Subnet] = []
        seen_ids: set[int] = set()
        for item in items:
            if not isinstance(item, dict):
                raise KeaError("Kea subnet entry is invalid")
            try:
                subnet_id = item["id"]
                prefix = item["subnet"]
            except KeyError as exc:
                raise KeaError("Kea subnet entry is invalid") from exc
            if (
                isinstance(subnet_id, bool)
                or not isinstance(subnet_id, int)
                or subnet_id <= 0
                or not isinstance(prefix, str)
                or not prefix.strip()
                or subnet_id in seen_ids
            ):
                raise KeaError("Kea subnet entry has an invalid or duplicate ID")
            seen_ids.add(subnet_id)
            shared_network = str(
                item.get("shared-network-name", item.get("shared-network", ""))
            ).strip()
            subnets.append(
                Subnet(
                    id=subnet_id,
                    prefix=prefix.strip(),
                    name=shared_network or prefix.strip(),
                )
            )
        return subnets

    async def get_leases(self, subnet_ids: list[int]) -> list[Lease]:
        if not subnet_ids:
            return []
        result = await self._command("lease4-get-all", {"subnets": subnet_ids})
        arguments = result.get("arguments", {})
        items = arguments.get("leases", []) if isinstance(arguments, dict) else []
        if not isinstance(items, list):
            raise KeaError("Kea lease list is invalid")
        leases: list[Lease] = []
        invalid_entries = 0
        for item in items:
            try:
                if not isinstance(item, dict):
                    raise TypeError
                state = int(item.get("state", 0))
                if state != 0:
                    continue
                raw_mac = str(item.get("hw-address", "")).strip()
                lease = Lease(
                    ip_address=str(item["ip-address"]),
                    hostname=str(item.get("hostname", "")).rstrip("."),
                    mac_address=normalize_mac(raw_mac) if raw_mac else None,
                    subnet_id=int(item["subnet-id"]),
                    starts_at=datetime.fromtimestamp(int(item["cltt"]), UTC),
                    valid_lifetime=timedelta(seconds=int(item["valid-lft"])),
                    state=state,
                )
                _ = lease.expires_at
                leases.append(lease)
            except KeyError, TypeError, ValueError, OSError, OverflowError:
                invalid_entries += 1
        if invalid_entries:
            LOGGER.warning(
                "Skipped %d invalid active lease entries returned by Kea",
                invalid_entries,
            )
        return leases

    async def is_reachable(self) -> bool:
        try:
            await self._command("status-get")
        except KeaError:
            return False
        return True

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def normalize_mac(value: str) -> str:
    """Return a canonical 48-bit colon-separated MAC address."""
    compact = "".join(character for character in value if character.isalnum()).lower()
    if len(compact) != 12 or any(
        character not in "0123456789abcdef" for character in compact
    ):
        raise ValueError("invalid MAC address")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))
