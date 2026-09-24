"""FastAPI application factory and HTML endpoints."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lease_lurker import __version__
from lease_lurker.i18n import select_locale, translator
from lease_lurker.kea import KeaProvider
from lease_lurker.providers import CompositeDeviceNameResolver
from lease_lurker.service import LeaseService, SnapshotUnavailableError
from lease_lurker.settings import Settings, load_settings
from lease_lurker.vendor import VendorLookup

LOGGER = logging.getLogger(__name__)
PACKAGE_DIR = Path(__file__).parent


def _remaining(expires_at: datetime, now: datetime) -> str:
    seconds = max(0, int((expires_at - now).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"


def create_app(
    settings: Settings | None = None,
    service: LeaseService | None = None,
) -> FastAPI:
    configured = settings or load_settings()
    lease_service = service or LeaseService(
        provider=KeaProvider(configured.kea),
        settings=configured,
        vendors=VendorLookup(),
        device_names=CompositeDeviceNameResolver(),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await lease_service.initialize()
        except Exception:
            LOGGER.exception("Kea capability check failed; readiness remains degraded")
        app.state.last_manual_refresh = 0.0
        yield
        await lease_service.close()

    app = FastAPI(
        title="LeaseLurker",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = configured
    app.state.lease_service = lease_service
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
    templates.env.filters["remaining"] = _remaining
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

    async def render_leases(
        request: Request,
        query: str,
        page: int,
        subnet: int | None = None,
        force: bool = False,
    ) -> HTMLResponse:
        return await _render_leases(
            request=request,
            query=query,
            page=page,
            subnet=subnet,
            force=force,
            service=lease_service,
            settings=configured,
            templates=templates,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return await render_leases(request, "", 1)

    @app.get("/leases", response_class=HTMLResponse)
    async def leases(
        request: Request,
        q: str = Query(default="", max_length=100),
        page: int = Query(default=1, ge=1),
        subnet: int | None = Query(default=None, ge=1),
    ) -> HTMLResponse:
        return await render_leases(request, q, page, subnet)

    @app.post("/refresh")
    async def refresh(
        request: Request,
        q: str = Form(default=""),
        subnet: int | None = Form(default=None, ge=1),
    ) -> RedirectResponse:
        now = time.monotonic()
        if now - app.state.last_manual_refresh >= 5:
            app.state.last_manual_refresh = now
            try:
                await lease_service.snapshot(force=True)
            except SnapshotUnavailableError:
                LOGGER.warning("Manual lease refresh failed")
        target = _lease_url(q, subnet)
        return RedirectResponse(target, status_code=303)

    @app.get("/locale/{locale}")
    async def locale(locale: str) -> RedirectResponse:
        selected = locale if locale in {"de", "en"} else configured.web.default_locale
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            "lease_lurker_locale",
            selected,
            max_age=31_536_000,
            httponly=True,
            samesite="lax",
        )
        return response

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> HTMLResponse:
        if await lease_service.ready():
            return HTMLResponse("ready", status_code=200)
        return HTMLResponse("not ready", status_code=503)

    return app


async def _render_leases(
    *,
    request: Request,
    query: str,
    page: int,
    subnet: int | None,
    force: bool,
    service: LeaseService,
    settings: Settings,
    templates: Jinja2Templates,
) -> HTMLResponse:
    locale = select_locale(
        request.cookies.get("lease_lurker_locale"),
        request.headers.get("accept-language"),
        settings.web.default_locale,
    )
    translate = translator(locale)
    try:
        snapshot_result = await service.snapshot(force=force)
    except SnapshotUnavailableError:
        return templates.TemplateResponse(
            request=request,
            name="unavailable.html",
            context={"locale": locale, "t": translate},
            status_code=503,
        )
    subnets = snapshot_result.snapshot.subnets
    visible_ids = {item.id for item in subnets}
    selected_subnet = subnet if subnet in visible_ids else None
    result = service.search(
        snapshot_result.snapshot, query, page, subnet_id=selected_subnet
    )
    now = datetime.now(snapshot_result.snapshot.refreshed_at.tzinfo)
    return templates.TemplateResponse(
        request=request,
        name="leases.html",
        context={
            "locale": locale,
            "t": translate,
            "query": query,
            "result": result,
            "subnets": subnets,
            "selected_subnet": selected_subnet,
            "lease_url": _lease_url,
            "snapshot": snapshot_result,
            "now": now,
        },
    )


def _lease_url(query: str, subnet: int | None = None, page: int = 1) -> str:
    parameters: dict[str, str | int] = {}
    if query:
        parameters["q"] = query
    if subnet is not None:
        parameters["subnet"] = subnet
    if page > 1:
        parameters["page"] = page
    return f"/leases?{urlencode(parameters)}" if parameters else "/leases"
