FROM python:3.12-slim

LABEL maintainer="badhope"
LABEL description="DATA-AI: multi-LLM agent runtime with RAG, memory and 30+ tools"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -e ".[all]"

RUN useradd -m -s /bin/bash dataai && \
    mkdir -p /app/data /app/config /app/logs && \
    chown -R dataai:dataai /app

USER dataai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from data_ai.sdk import create_client; print('OK')"

ENTRYPOINT ["data-ai"]