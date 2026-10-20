FROM ghcr.io/astral-sh/uv:0.13.2 AS uv

FROM python:3.14-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/collector/pyproject.toml services/collector/pyproject.toml
COPY network/pyproject.toml network/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package netpulse-collector
COPY packages/core packages/core
COPY services/collector services/collector
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package netpulse-collector

FROM python:3.14-slim-trixie AS runtime
RUN groupadd --system netpulse && useradd --system --gid netpulse --no-create-home netpulse
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
USER netpulse
CMD ["netpulse-collector"]
