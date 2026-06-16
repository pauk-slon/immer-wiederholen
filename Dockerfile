ARG VENV=/opt/venv

FROM python:3.14-slim AS build
ARG VENV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=$VENV
ENV PATH="$VENV/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim AS dev
ARG VENV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY --from=build $VENV $VENV
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=$VENV
ENV PATH="$VENV/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen
COPY . .
CMD ["python", "-m", "iwh.bot"]

FROM python:3.14-slim AS prod
ARG VENV
COPY --from=build $VENV $VENV
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=$VENV
ENV PATH="$VENV/bin:$PATH"
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/uv \
    /uv sync --frozen --no-dev
CMD ["python", "-m", "iwh.bot"]
