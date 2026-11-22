# syntax is plain Dockerfile on purpose: no remote frontend image to fetch.
# API image (docs/02 section 7, docs/09 section 9). Build from the repo root:
#   docker build -f backend/Dockerfile .

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_NO_CACHE=1 \
    EHR_MIP_ROOT=/app
RUN pip install --no-cache-dir --root-user-action=ignore uv==0.13.7
WORKDIR /build
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --extra redis --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev --extra redis --no-editable

# The embedding model, baked outside the data volume so the API starts without internet.
FROM build AS model
RUN ["/app/.venv/bin/python", "-c", "from pathlib import Path; from ehr_mip.config import Settings; from ehr_mip.search.embedder import SentenceTransformerEmbedder; e = SentenceTransformerEmbedder(Settings().embedding_model, Path('/opt/hf-cache')); print('baked', e.model_name)"]

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
# Security fixes published since the pinned base was built.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade --yes --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
# pip is not needed at run time and only adds findings to the image scan.
RUN pip uninstall --yes --root-user-action=ignore pip \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data/generated \
    && chown 10001:10001 /app/data/generated
COPY --from=build /app/.venv /app/.venv
COPY --from=model /opt/hf-cache /opt/hf-cache
COPY data/raw /app/data/raw
WORKDIR /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EHR_MIP_ROOT=/app \
    ENV=prod \
    HOME=/tmp \
    HF_HOME=/opt/hf-cache \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    REPORTS_DIR=/app/data/generated/reports
USER 10001:10001
EXPOSE 8000
CMD ["ehr-mip", "serve", "--host", "0.0.0.0", "--port", "8000"]
