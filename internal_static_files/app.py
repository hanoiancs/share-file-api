from fastapi import FastAPI

from internal_static_files import models as _models
from internal_static_files.auth import router as auth_router
from internal_static_files.database import Base
from internal_static_files.files import router as files_router

_ = _models


def create_app() -> FastAPI:
    app = FastAPI(title="Internal Static Files API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(files_router)
    return app


__all__ = ["Base", "create_app"]
