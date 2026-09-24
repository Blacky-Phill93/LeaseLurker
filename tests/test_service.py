from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from lease_lurker.service import LeaseService, SnapshotUnavailableError
from lease_lurker.vendor import VendorLookup

from .conftest import FakeProvider, NoNames, make_lease


async def test_snapshot_filters_and_enriches(settings, now) -> None:
    provider = FakeProvider(
        [
            make_lease(now),
            make_lease(now, hostname="client-id-only", mac=None),
            make_lease(now, subnet_id=2),
            make_lease(now, hostname="expired", lifetime=-1),
            make_lease(now, hostname="reclaimed", state=1),
        ]
    )
    service = LeaseService(
        provider,
        settings,
        VendorLookup({6: {"001122": "Example Vendor"}}),
        NoNames(),
        clock=lambda: now,
    )
    result = await service.snapshot()
    assert len(result.snapshot.leases) == 2
    assert result.snapshot.leases[0].subnet.name == "Office"
    assert result.snapshot.leases[0].vendor == "Example Vendor"
    assert result.snapshot.leases[1].lease.mac_address is None
    assert result.snapshot.leases[1].vendor is None
    assert provider.calls == 1
    assert (await service.snapshot()).snapshot is result.snapshot


async def test_search_normalizes_mac_and_paginates(settings, now) -> None:
    leases = [
        make_lease(now, hostname=f"PC-{index:03}", mac=f"00:11:22:33:44:{index:02x}")
        for index in range(12)
    ]
    service = LeaseService(
        FakeProvider(leases), settings, VendorLookup({}), NoNames(), clock=lambda: now
    )
    snapshot = (await service.snapshot()).snapshot
    hostname = service.search(snapshot, "pc-00", 1)
    assert hostname.total == 10
    mac = service.search(snapshot, "33-44-0a", 1)
    assert mac.total == 1
    second_page = service.search(snapshot, "", 2)
    assert second_page.total == 12
    assert len(second_page.items) == 2
    assert service.search(snapshot, "x", 1).total == 0


async def test_stale_snapshot_is_served_then_expires(settings, now) -> None:
    current = [now]
    provider = FakeProvider([make_lease(now)])
    service = LeaseService(
        provider, settings, VendorLookup({}), NoNames(), clock=lambda: current[0]
    )
    await service.initialize()
    first = await service.snapshot()
    provider.fail = True
    current[0] += timedelta(seconds=31)
    stale = await service.snapshot()
    assert stale.stale is True
    assert stale.snapshot is first.snapshot
    assert await service.ready() is True
    current[0] += timedelta(seconds=301)
    with pytest.raises(SnapshotUnavailableError, match="too old"):
        await service.snapshot()
    assert await service.ready() is False


async def test_initial_failure_has_no_snapshot(settings, now) -> None:
    service = LeaseService(
        FakeProvider([], fail=True),
        settings,
        VendorLookup({}),
        NoNames(),
        clock=lambda: now,
    )
    with pytest.raises(SnapshotUnavailableError, match="No lease"):
        await service.snapshot()


async def test_refresh_is_single_flight(settings, now) -> None:
    class SlowProvider(FakeProvider):
        async def get_leases(self, subnet_ids):
            await asyncio.sleep(0.01)
            return await super().get_leases(subnet_ids)

    provider = SlowProvider([make_lease(now)])
    service = LeaseService(
        provider, settings, VendorLookup({}), NoNames(), clock=lambda: now
    )
    await asyncio.gather(service.snapshot(), service.snapshot(), service.snapshot())
    assert provider.calls == 1
    await service.initialize()
    assert provider.capabilities_checked
    await service.close()
    assert provider.closed
