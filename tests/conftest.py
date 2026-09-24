from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lease_lurker.models import Lease, Subnet
from lease_lurker.settings import Settings


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "kea": {"url": "http://kea.test/"},
            "cache": {"ttl_seconds": 30, "stale_after_seconds": 300},
            "subnets": [
                {"id": 1, "visible": True, "name": "Office"},
                {"id": 2, "visible": False},
            ],
            "web": {"default_locale": "de", "page_size": 10},
        }
    )


def make_lease(
    now: datetime,
    *,
    hostname: str = "pc-042.example.test",
    mac: str | None = "00:11:22:33:44:55",
    subnet_id: int = 1,
    state: int = 0,
    lifetime: int = 3600,
) -> Lease:
    return Lease(
        ip_address="192.0.2.42",
        hostname=hostname,
        mac_address=mac,
        subnet_id=subnet_id,
        starts_at=now,
        valid_lifetime=timedelta(seconds=lifetime),
        state=state,
    )


class FakeProvider:
    def __init__(self, leases: list[Lease], *, fail: bool = False) -> None:
        self.leases = leases
        self.fail = fail
        self.capabilities_checked = False
        self.closed = False
        self.calls = 0

    async def check_capabilities(self) -> None:
        self.capabilities_checked = True
        if self.fail:
            raise RuntimeError("offline")

    async def get_subnets(self) -> list[Subnet]:
        if self.fail:
            raise RuntimeError("offline")
        return [
            Subnet(id=1, prefix="192.0.2.0/24", name="from-kea"),
            Subnet(id=2, prefix="198.51.100.0/24", name="secret"),
        ]

    async def get_leases(self, subnet_ids: list[int]) -> list[Lease]:
        self.calls += 1
        assert subnet_ids == [1]
        if self.fail:
            raise RuntimeError("offline")
        return self.leases

    async def is_reachable(self) -> bool:
        return not self.fail

    async def close(self) -> None:
        self.closed = True


class NoNames:
    @property
    def name(self) -> str:
        return "none"

    def resolve(self, mac_address: str) -> str | None:
        return None
