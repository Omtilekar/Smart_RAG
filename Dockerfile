# Task 4.11 - deployment container for the Task 4.10 FastAPI service
# (src/api/app.py:create_app). CPU-only: the frozen Phase 4 serving
# decision is continuously-warm CPU Fargate (project_plan/
# SERVING_FEASIBILITY.md), so this image deliberately never installs
# requirements-gpu.txt's CUDA torch build - see requirements-cpu.txt.
#
# Runtime scope, honestly stated: the dense route this container serves
# is wired to the Phase 1 development LanceDB index (162,357 rows,
# BAAI/bge-small-en-v1.5) per Task 4.10's documented, explicit
# limitation (src/api/dependencies.py) - NOT the 10,487,096-row
# full-corpus production index. See project_plan/PHASE4_DEPLOYMENT.md.
#
# Large runtime artifacts (the dev LanceDB index, ~470 MB; data/xbrl.duckdb,
# ~6.7 GB) are never copied into this image - they are mounted read-only
# at container run time (see project_plan/PHASE4_DEPLOYMENT.md's "Artifact
# strategy"). Only the small embedding model (~130 MB) is baked in, at a
# pinned revision, so the container never downloads it at runtime.

FROM python:3.11-slim AS base

# HF_HOME pinned to a fixed, non-default path so the model download
# below lands somewhere predictable, and so HF_HUB_OFFLINE=1 has one
# unambiguous cache directory to refuse to escape at runtime
# (src/embeddings/bge.py's own offline-only contract).
ENV HF_HOME=/opt/hf-cache \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# --- dependency layers (cached separately from application code) ---
COPY requirements-cpu.txt requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements-cpu.txt \
    && python -m pip install --no-cache-dir -r requirements.txt

# --- pre-stage the pinned embedding model, once, at build time ---
# Pinned to the exact repo+revision src/embeddings/bge.py requires
# (BAAI/bge-small-en-v1.5 @ 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a).
# A network call happens here, during build, not at container startup -
# consistent with "no runtime downloads" (project_plan-mandated) while
# still keeping the pin identical to the one load_model() itself verifies.
RUN python -c "\
from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='BAAI/bge-small-en-v1.5', revision='5c38ec7c405ec4b44b94cc5a9bb96e735b38267a')"

# HF_HUB_OFFLINE is set only now, after the pinned download above - it must
# not be set during the RUN step itself, or huggingface_hub refuses the
# download it's meant to make redundant at every step after this one.
ENV HF_HUB_OFFLINE=1

# --- application code (only what the deployed service imports) ---
COPY src/ ./src/
COPY configs/eval_tags.yaml ./configs/eval_tags.yaml

# Non-root runtime user; the image ships no writable source tree
# requirement (the service never writes under /app at runtime - LanceDB/
# duckdb paths are read-only mounts under /app/artifacts, /app/data).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app "$HF_HOME"
USER appuser

# DEVICE=cpu is explicit, not inferred from CUDA's absence - matches the
# frozen CPU-Fargate serving decision even if this exact image is ever run
# on a GPU host by accident. STORAGE_ROOT/GENERATION_PROVIDER/
# GENERATION_MODEL/OPENROUTER_API_KEY are intentionally NOT set here -
# see project_plan/PHASE4_DEPLOYMENT.md's "Secrets" and "Artifact
# strategy" sections for how they're supplied at run time.
ENV DEVICE=cpu \
    APP_ENV=production \
    LOG_LEVEL=INFO

EXPOSE 8000

# No --reload (never in production), one worker by default (heavy
# resident model/index state - see project_plan/PHASE4_DEPLOYMENT.md's
# "Worker count" section for why this isn't a throughput claim).
ENTRYPOINT ["python", "-m", "uvicorn", "src.api.app:create_app", "--factory", \
            "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
