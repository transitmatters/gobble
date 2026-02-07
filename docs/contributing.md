# Contributing

Thank you for your interest in contributing to Gobble! This guide will help you get set up and familiar with the development workflow.

## Getting started

1. Clone the repository and create your new branch with `bash git checkout -b my-branch-with-cool-new-features`
2. Install [uv](https://docs.astral.sh/uv/) and Python 3.13
3. Set up your environment:

```bash
uv venv --python 3.13
uv sync --group dev
uv run pre-commit install
```

1. Copy `config/template.json` to `config/local.json` and add your [MBTA V3 API key](https://api-v3.mbta.com/)

## Running locally

```bash
uv run src/gobble.py
```

!!! tip
    Set `"modes": ["rapid"]` in your `config/local.json` to reduce API load and output volume during development.

## Running tests

```bash
uv run pytest
```

To run with coverage:

```bash
uv run coverage run -m pytest
uv run coverage report
```

## Linting and formatting

Gobble uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting. Pre-commit hooks run these automatically, but you can also run them manually:

```bash
uv run ruff check --fix src
uv run ruff format src
```

## Code style

- Ruff handles formatting and lint rules
- Not required but highly encouraged:
  - Google-style docstrings
  - Type hints
  - Unit Testing with PyTest

## Pull request workflow

1. Create a feature branch from `main`
2. Make your changes
3. Ensure tests pass (`uv run pytest`)
4. Ensure linting passes (`uv run ruff check src`)
5. Open a pull request against `main`
6. CI will run tests and linting automatically

## Building the docs

```bash
uv sync --group docs
uv run mkdocs serve
```

This starts a local server at `http://127.0.0.1:8000` with live reload.

## Project structure

```
src/
├── gobble.py          # Main entry point, SSE client, threading
├── event.py           # Event detection and enrichment
├── gtfs.py            # GTFS archive management and schedule queries
├── trip_state.py      # Trip state tracking and persistence
├── disk.py            # CSV file writing
├── s3_upload.py       # S3 upload
├── util.py            # Date/time and path utilities
├── config.py          # Configuration loading
├── constants.py       # Route and stop definitions
├── logger.py          # Logging setup
├── timing.py          # Performance measurement
└── tests/             # Test suite
```
