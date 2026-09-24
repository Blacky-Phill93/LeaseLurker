"""Provider-independent domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class Lease:
    ip_address: str
    hostname: str
    mac_address: str | None
    subnet_id: int
    starts_at: datetime
    valid_lifetime: timedelta
    state: int = 0

    @property
    def expires_at(self) -> datetime:
        return self.starts_at + self.valid_lifetime

    def is_active(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return self.state == 0 and self.expires_at > current


@dataclass(frozen=True, slots=True)
class Subnet:
    id: int
    prefix: str
    name: str


@dataclass(frozen=True, slots=True)
class LeaseView:
    lease: Lease
    subnet: Subnet
    vendor: str | None
    device_name: str | None


@dataclass(frozen=True, slots=True)
class LeaseSnapshot:
    leases: tuple[LeaseView, ...]
    subnets: tuple[Subnet, ...]
    refreshed_at: datetime
