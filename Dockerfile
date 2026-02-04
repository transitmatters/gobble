FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-editable

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
