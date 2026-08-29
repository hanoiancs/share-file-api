from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import models as _models
from app.auth import router as auth_router
from app.auth import set_access_token_cookie
from app.config import get_settings
from app.database import Base
from app.files import router as files_router

_ = _models

ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]


def create_app() -> FastAPI:
    app = FastAPI(title="Internal Static Files API", root_path="/api")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "OK"}

    @app.middleware("http")
    async def persist_access_token_query_param(request, call_next):
        access_token = request.query_params.get("access_token")
        if access_token:
            query = [
                (key, value)
                for key, value in request.query_params.multi_items()
                if key != "access_token"
            ]
            url = urlsplit(str(request.url))
            path = url.path
            root_path = request.scope.get("root_path", "")
            if root_path and not path.startswith(root_path):
                path = f"{root_path}{path}"
            redirect_url = urlunsplit(
                (url.scheme, url.netloc, path, urlencode(query), url.fragment)
            )
            response = RedirectResponse(redirect_url)
            set_access_token_cookie(response, access_token, get_settings())
            return response
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(files_router)
    return app


__all__ = ["Base", "create_app"]
