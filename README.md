# gobble

![Screenshot in action](docs/screenshot.png)

## Requirements to develop locally

- node

## Development Instructions

1. Add `MBTA_V3_API_KEY` and `MBTA_GTFS_UNZIPPED` to your shell environment:
   - `export MBTA_V3_API_KEY='KEY'` in ~/.bashrc or ~/.zshrc
   - `export MBTA_GTFS_UNZIPPED='/path/to/gtfs'` in ~/.bashrc or ~/.zshrc
1. In the root directory, run `npm install` to install dependencies
1. Run `npm run build && npm start` to start.
1. Output will be in `output/` in your current working directory. Good luck!

### Linting

To lint, run `npm run lint` in the root directory.


## Support TransitMatters

If you've found this app helpful or interesting, please consider [donating](https://transitmatters.org/donate) to TransitMatters to help support our mission to provide data-driven advocacy for a more reliable, sustainable, and equitable transit system in Metropolitan Boston.
