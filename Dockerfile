# syntax=docker/dockerfile:1.4
# Enable BuildKit features for faster builds

# ============================================
# Stage 1: Base Python Image with System Deps
# ============================================
FROM python:3.11-slim AS base

# Install system dependencies once (cached layer)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    libsndfile1 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Stage 2: Python Dependencies Builder
# ============================================
FROM base AS dependencies

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel (cached layer)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Copy ONLY requirements first (better caching)
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies with pip cache
# This layer will be cached unless requirements.txt changes
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ============================================
# Stage 3: Runtime Image
# ============================================
FROM python:3.11-slim AS runtime

# Install ONLY runtime dependencies (no build tools)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Create directories with proper permissions (cached layer)
RUN mkdir -p uploads logs tmp config data && \
    chown -R appuser:appuser uploads logs tmp config data && \
    chmod 755 uploads logs tmp config data

# Copy static files first (changes less frequently = better caching)
COPY --chown=appuser:appuser ./requirements.txt ./requirements.txt
COPY --chown=appuser:appuser ./.env ./.env
COPY --chown=appuser:appuser ./service-account-key.json ./service-account-key.json

# Copy whitelist config
COPY --chown=appuser:appuser ./whitelist_config.py ./whitelist_config.py
COPY --chown=appuser:appuser ./whitelist_config.py ./config/whitelist_config.py

# Copy application code LAST (changes most frequently)
# This ensures code changes don't invalidate dependency cache
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./bot_main.py ./bot_main.py

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app:/app/app

# Switch to non-root user
USER appuser

# Optimized health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "from app.config import settings; print('OK')" || exit 1

# Expose application port
EXPOSE 8000

# Use tini for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Start the application
CMD ["python", "bot_main.py"]
