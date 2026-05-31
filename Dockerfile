FROM python:3.14-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 1. Set environment variables early
ENV UV_NO_DEV=1 \
    # Compiles .py files to .pyc during sync for faster startup performance
    UV_COMPILE_BYTECODE=1 \
    # Prevents Python from writing .pyc files to disk at runtime (since uv already compiled them)
    PYTHONDONTWRITEBYTECODE=1 \
    # Forces stdout/stderr streams to be unbuffered so FastAPI logs appear instantly
    PYTHONUNBUFFERED=1

WORKDIR /app

# 2. Leverage Docker Layer Caching for dependencies
# Copy ONLY the package configuration and lockfile first
COPY pyproject.toml uv.lock ./

# Mount a cache directory so uv doesn't redownload packages on minor lockfile updates
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# 3. Copy the rest of the application source code
# (Changes here will no longer trigger a full pip/uv reinstall)
COPY . .
RUN mv .env.prod .env
# 4. Final sync to install the project itself (fast, since dependencies are cached)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]

CMD ["uv", "run", "--env-file", ".env", "fastapi", "run", "main.py", "--port", "80"]