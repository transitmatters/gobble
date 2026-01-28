# gobble
![lint](https://github.com/transitmatters/gobble/actions/workflows/lint.yml/badge.svg?branch=main)
![test](https://github.com/transitmatters/gobble/actions/workflows/test.yml/badge.svg?branch=main)
![deploy](https://github.com/transitmatters/gobble/actions/workflows/deploy.yml/badge.svg?branch=main)

![Screenshot in action](docs/screenshot.png)

Gobble is a service that reads the [MBTA V3 Streaming API](https://www.mbta.com/developers/v3-api/streaming) for all train/bus events, and writes them out to a format that can be understood by the [TransitMatters Data Dashboard](https://github.com/transitmatters/t-performance-dash).

## Requirements to develop locally

- [`uv`](https://docs.astral.sh/uv/) with Python 3.12
  - Ensure `uv` is using the correct Python version by running `uv venv --python 3.12`

## Development Instructions

1. Duplicate `config/template.json` into `config/local.json`, and change the null out with your MBTA V3 API key.
2. In the root directory, run `uv sync --group dev` to install dependencies followed by `uv run pre-commit install` to install pre-commit hooks
3. Run `uv run src/gobble.py` to start.
4. Output will be in `data/` in your current working directory. Good luck!

### Container

You can also run Gobble inside a container using the following `docker build` and `docker run` commands

```bash
docker build -t gobble -f Containerfile .
docker run \
    -v ./config/local.json:/app/config/local.json:z \
    -v ./data:/app/data:z \
    gobble:latest
```

Output will be in `data/` in your current working directory. Good luck!

### Linting

You can run the linter against any code changes with the following commands

```bash
$ uv run ruff check --fix src
$ uv run ruff format src
```

## Support TransitMatters

If you've found this app helpful or interesting, please consider [donating](https://transitmatters.org/donate) to TransitMatters to help support our mission to provide data-driven advocacy for a more reliable, sustainable, and equitable transit system in Metropolitan Boston.
