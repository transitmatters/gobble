FROM python:3.13-slim

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

ENTRYPOINT ["uv", "run", "python3", "src/gobble.py"]
