"""Discovery import must not overwrite HTTP/TCP service health from ARP."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.discovery_import import import_discovery_hosts
from app.models import AppSettings, Service
from app.schemas import DiscoveryHostEntry


class DiscoveryImportHealthDecouplingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "test.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self._tmp.cleanup()

    async def _seed_service(
        self,
        db: AsyncSession,
        *,
        host: str,
        port: int,
        protocol: str,
        is_online: bool,
    ) -> Service:
        svc = Service(
            name=f"{host}:{port}",
            url=f"http://{host}:{port}" if port else f"host://{host}",
            host=host,
            port=port,
            protocol=protocol,
            auto_discovered=True,
            is_online=is_online,
            last_checked=datetime.now(timezone.utc),
        )
        db.add(svc)
        await db.commit()
        return svc

    async def test_discovery_offline_does_not_touch_port_services(self) -> None:
        async with self.session_factory() as db:
            await self._seed_service(db, host="192.168.1.201", port=0, protocol="host", is_online=True)
            await self._seed_service(db, host="192.168.1.201", port=3000, protocol="http", is_online=True)
            await self._seed_service(db, host="192.168.1.201", port=8000, protocol="http", is_online=True)

            await import_discovery_hosts(
                db,
                [DiscoveryHostEntry(ip="192.168.1.201", online=False)],
                source="test",
                source_hostname="test",
                mark_missing_offline=False,
            )

            rows = (await db.execute(select(Service).order_by(Service.port))).scalars().all()
            by_port = {s.port: s for s in rows}
            self.assertFalse(by_port[0].is_online)
            self.assertTrue(by_port[3000].is_online)
            self.assertTrue(by_port[8000].is_online)

    async def test_mark_missing_offline_only_affects_host_rows(self) -> None:
        async with self.session_factory() as db:
            db.add(AppSettings())
            await self._seed_service(db, host="192.168.1.200", port=0, protocol="host", is_online=True)
            await self._seed_service(db, host="192.168.1.200", port=3000, protocol="http", is_online=True)

            await import_discovery_hosts(
                db,
                [DiscoveryHostEntry(ip="192.168.1.1", online=True)],
                source="test",
                source_hostname="test",
                mark_missing_offline=True,
            )

            rows = (await db.execute(select(Service).where(Service.host == "192.168.1.200"))).scalars().all()
            by_port = {s.port: s for s in rows}
            self.assertFalse(by_port[0].is_online)
            self.assertTrue(by_port[3000].is_online)

    async def test_offline_scope_skips_hosts_outside_cidr(self) -> None:
        async with self.session_factory() as db:
            db.add(AppSettings())
            await self._seed_service(db, host="192.168.1.150", port=0, protocol="host", is_online=True)
            await self._seed_service(db, host="192.168.1.200", port=0, protocol="host", is_online=True)

            await import_discovery_hosts(
                db,
                [DiscoveryHostEntry(ip="192.168.1.151", online=True)],
                source="test",
                source_hostname="test",
                mark_missing_offline=True,
                offline_scope_cidrs=["192.168.1.144/28"],
            )

            rows = (await db.execute(select(Service).where(Service.port == 0))).scalars().all()
            by_host = {s.host: s for s in rows}
            self.assertFalse(by_host["192.168.1.150"].is_online)
            self.assertTrue(by_host["192.168.1.200"].is_online)


if __name__ == "__main__":
    unittest.main()
