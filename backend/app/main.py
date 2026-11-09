"""FastAPI application: wiring, middleware, error shape and static SPA hosting."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .config import REPO_ROOT, Settings, get_settings
from .db import db_healthy, init_db
from .errors import AppError

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("relayops")

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"

STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": {**(details or {}), "request_id": request_id_ctx.get()},
        }
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line, so logs stay greppable in a container."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    if any(isinstance(handler.formatter, JsonLogFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    logging.getLogger("uvicorn.access").disabled = True


class SPAStaticFiles(StaticFiles):
    """Serve the built SPA, falling back to index.html so client-side routes deep-link."""

    async def get_response(self, path: str, scope: Any) -> Any:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # StaticFiles normalises with os.path, so compare on POSIX separators.
            normalised = path.replace("\\", "/").lstrip("/")
            is_api_or_asset = normalised == "api" or normalised.startswith(("api/", "assets/"))
            # Client-side routes deep-link to index.html; API and asset misses stay honest 404s.
            if exc.status_code == 404 and not is_api_or_asset:
                return await super().get_response("index.html", scope)
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    settings.check_prod_safety()
    init_db()
    logger.info(
        "RelayOps starting",
        extra={
            "extra_fields": {
                "version": __version__,
                "env": settings.env,
                "llm_mode": settings.llm_mode,
                "database_url": settings.database_url,
            }
        },
    )
    if settings.seed_on_start:
        # P04 replaces this with the demo dataset and demo users.
        logger.info("SEED_ON_START is on; demo dataset seeding lands in P04")
    yield
    logger.info("RelayOps shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="RelayOps API",
        version=__version__,
        description="Traceable, human-verified handovers from scattered project activity.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "%s %s raised",
                request.method,
                request.url.path,
                extra={"extra_fields": {"request_id": request_id}},
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                }
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ").title()
        return error_response(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed",
            {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return error_response(500, "INTERNAL_ERROR", "Unexpected server error")

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, Any]:
        db_ok = db_healthy()
        return {
            "status": "ok" if db_ok else "degraded",
            "version": __version__,
            "llm_mode": settings.llm_mode,
            "db": "ok" if db_ok else "error",
        }

    from .routers import auth, users

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
    else:

        @app.get("/", include_in_schema=False)
        def _no_build() -> dict[str, Any]:
            return {
                "app": "RelayOps",
                "frontend": "not built",
                "hint": "Run `npm run build` (or use the Vite dev server on :5173).",
                "api": "/api/v1/health",
            }

    return app


app = create_app()
