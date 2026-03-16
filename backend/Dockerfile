FROM python:3.12-slim

WORKDIR /app

# System dependencies (curl for healthcheck, build-essential for miniaudio C extension)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache friendly)
# CFLAGS: miniaudio 1.2 C extension needs -Wno-implicit-function-declaration on gcc 14
COPY requirements.txt .
RUN CFLAGS="-Wno-implicit-function-declaration" pip install --no-cache-dir --upgrade pip \
    && CFLAGS="-Wno-implicit-function-declaration" pip install --no-cache-dir -r requirements.txt

# Application source
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=25s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Single worker is correct for Container Apps consumption plan (scale-out, not scale-up)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
