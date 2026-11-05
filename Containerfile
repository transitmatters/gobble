FROM python:3.14-slim

WORKDIR /app

# Install uv for Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy source code
COPY . .

# Install dependencies
RUN uv sync

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
# Cap glibc malloc arenas so many threads don't each hold on to freed memory
ENV MALLOC_ARENA_MAX=2

ENTRYPOINT ["uv", "run", "python3", "src/gobble.py"]
