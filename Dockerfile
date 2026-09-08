    FROM python:3.14.4-slim AS builder

    # Set environment variables
    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1

    # Set working directory
    WORKDIR /app

    # Install build dependencies for PostgreSQL and compilation
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        pkg-config && \
        rm -rf /var/lib/apt/lists/*

    # Build Python wheels
    COPY requirements.txt .
    RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

    # --- Final Stage ---
    FROM python:3.14.4-slim

    WORKDIR /app

    # Install runtime PostgreSQL library
    RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 && \
        rm -rf /var/lib/apt/lists/*

    # Install pre-built wheels from builder
    COPY --from=builder /app/wheels /wheels
    COPY --from=builder /app/requirements.txt .
    RUN pip install --no-cache-dir /wheels/*

    # Copy project code into container

    COPY . .    