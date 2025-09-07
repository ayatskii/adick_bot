# Production-optimized multi-stage build
FROM python:3.11-slim AS dependencies

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install wheel for faster builds
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage - clean lightweight image
FROM python:3.11-slim AS runtime

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from build stage
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root application user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./bot_main.py ./bot_main.py
COPY --chown=appuser:appuser ./test_api.py ./test_api.py
COPY --chown=appuser:appuser ./requirements.txt ./requirements.txt

# Set working directory to /app and add to Python path
WORKDIR /app
ENV PYTHONPATH=/app:/app/app

# Create necessary directories with proper permissions
RUN mkdir -p uploads logs tmp && \
    chown -R appuser:appuser uploads logs tmp && \
    chmod 755 uploads logs tmp

# Verify the app module structure
RUN python -c "import sys; print('Python path:', sys.path); import app.config; print('app.config imported successfully')"

# Switch to non-root user
USER appuser

# Environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.path.append('/app'); from app.config import settings; print('Health check passed')" || exit 1

# Expose application port (for future web interface)
EXPOSE 8000

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Start the application (can be overridden for different modes)
CMD ["python", "bot_main.py"]
