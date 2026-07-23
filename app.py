import os

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from db import init_db
from limiter import limiter


def create_app(static_dir: str) -> FastAPI:
    # Import models before creating tables
    import models  # noqa: F401 — ensures tables are registered on Base.metadata
    init_db()

    from routes import api

    app = FastAPI()

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS_ORIGINS: comma-separated list of allowed origins.
    # In production, set this to your domain, e.g. "https://crm.example.com".
    # Defaults to "*" (open) only when explicitly left unset — fine for
    # same-origin production deployments; set it for any public-facing deployment.
    _raw_origins = os.environ.get("CORS_ORIGINS", "*")
    _origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    # allow_credentials=True is incompatible with wildcard origins per the CORS spec.
    _credentials = _origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes first — these take priority in FastAPI routing
    app.include_router(api, prefix="/api")

    # Health check on API router — must be defined before include_router
    # Actually, adding to api after include_router won't work.
    # Add directly to app instead:
    @app.get("/api/health", include_in_schema=False)
    def health():
        return {"ok": True}

    # Static files + SPA fallback
    if os.path.isdir(static_dir):
        assets_dir = os.path.join(static_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Catch-all for SPA — must not match /api/* paths
        @app.api_route("/{path:path}", methods=["GET"], include_in_schema=False)
        async def spa_fallback(request: Request, path: str):
            # Skip API routes — they should have been handled by the router
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)

            # Serve static file if it exists
            file_path = os.path.join(static_dir, path)
            if path and os.path.isfile(file_path):
                return FileResponse(file_path)

            # SPA fallback
            return FileResponse(
                os.path.join(static_dir, "index.html"),
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

    return app


asgi = create_app("./dist")
