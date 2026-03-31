# === Stage 1: Build ===
FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with CPU-only torch
# CRITICAL: torch==2.11.0+cpu pinned explicitly to prevent pip resolving CUDA variant from PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch==2.11.0+cpu \
    -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.11-slim
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code and data
COPY src/ src/
COPY data/ data/
COPY .env.example .env.example
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "chemtrace", "status"]
