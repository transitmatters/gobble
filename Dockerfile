FROM python:3.12-slim

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==2.0.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Copy application source code
COPY src/ ./src/

# Copy entrypoint script
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create data directory for outputs
RUN mkdir -p /app/data

# Create non-root user for security (optional but recommended)
RUN useradd -m -u 1000 gobble && \
    chown -R gobble:gobble /app

# Health check - check if trip_states directory exists and contains files
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD test -d /app/data/trip_states && [ "$(find /app/data/trip_states -type f | wc -l)" -gt 0 ] || exit 1

# Run the entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]
