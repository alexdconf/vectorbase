# ── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.14-slim

# Install uv from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Keep Python from writing .pyc files and from buffering stdout/stderr.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # django
    DEBUG=True \
    ALLOWED_HOSTS=localhost,127.0.0.1 \
    # postgres
    VECTORS_DB_NAME=postgres \
    VECTORS_DB_USER=postgres \
    VECTORS_DB_HOST=localhost \
    VECTORS_DB_PORT=5432 \
    # vectorbase
    SCHEMA_CONFIG_PATH=schema.yaml \
    SEARCH_RATE_LIMIT=100/d \
    GLOBAL_DAILY_QUOTA=10000

WORKDIR /app

# ── Install dependencies ─────────────────────────────────────────────────────
# Copy lockfiles first so this layer is cached independently of app source.
# Rebuilds only when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Add the virtualenv to PATH for all subsequent RUN / ENTRYPOINT / CMD steps.
ENV PATH="/app/.venv/bin:$PATH"

# ── Copy application source ──────────────────────────────────────────────────
COPY vectorbase/ ./vectorbase/
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# ── Collect static files ─────────────────────────────────────────────────────
# Django requires SECRET_KEY to be set even for management commands.
# A placeholder is used here; the real key must be injected at runtime.
# WhiteNoise compresses and fingerprints the files during this step.
RUN SECRET_KEY=build-placeholder \
    DEBUG=False \
    python vectorbase/manage.py collectstatic --noinput

# ── Security: run as a non-root user ────────────────────────────────────────
RUN adduser --disabled-password --gecos '' --home /app appuser \
    && chown -R appuser /app
USER appuser

# ── Runtime ──────────────────────────────────────────────────────────────────
# Set the working directory to the Django project root so that gunicorn can
# resolve the `vectorbase.wsgi` module and manage.py commands work without
# specifying a path.
WORKDIR /app/vectorbase

EXPOSE 8000

# WEB_CONCURRENCY — number of gunicorn worker processes (default: 4).
# PORT            — port to bind (default: 8000).
# Both can be overridden at `docker run` time with -e.
ENV WEB_CONCURRENCY=4 \
    PORT=8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
