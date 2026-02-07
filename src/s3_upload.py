import argparse
import datetime
import glob
import gzip
import logging
import os
import time
from io import BytesIO

import boto3
from ddtrace import tracer

from config import CONFIG
from disk import DATA_DIR
from logger import set_up_logging
from util import EASTERN_TIME, service_date

logging.basicConfig(level=logging.INFO, filename="s3_upload.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

s3 = boto3.client("s3")

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "daily-*/*/Year={year}/Month={month}/Day={day}/events.csv")
S3_DATA_TEMPLATE = "Events-live/{relative_path}.gz"


@tracer.wrap()
def _compress_and_upload_file(fp: str):
    """Compress a file in-memory and upload to S3."""
    # generate output location
    rp = os.path.relpath(fp, DATA_DIR)
    s3_key = S3_DATA_TEMPLATE.format(relative_path=rp)

    with open(fp, "rb") as f:
        # gzip to buffer and upload
        gz_bytes = gzip.compress(f.read())
        buffer = BytesIO(gz_bytes)

        s3.upload_fileobj(
            buffer, S3_BUCKET, Key=s3_key, ExtraArgs={"ContentType": "text/csv", "ContentEncoding": "gzip"}
        )


@tracer.wrap(service="gobble")
def upload_todays_events_to_s3():
    """Upload today's events to the TM s3 bucket."""
    start_time = time.time()

    logger.info("Beginning upload of recent events to s3.")
    pull_date = service_date(datetime.datetime.now(EASTERN_TIME))

    # get files updated for this service date
    # TODO: only update modified files? cant imagine much of a difference if we partition live data by day
    files_updated_today = glob.glob(
        LOCAL_DATA_TEMPLATE.format(year=pull_date.year, month=pull_date.month, day=pull_date.day)
    )

    # upload them to s3, gzipped
    for fp in files_updated_today:
        _compress_and_upload_file(fp)

    end_time = time.time()
    logger.info(f"Uploaded {len(files_updated_today)} files to s3, took {end_time - start_time} seconds.")


@tracer.wrap(service="gobble")
def backfill_events_to_s3(start_date: datetime.date):
    """
    Backfill events to S3 from a specified date up to today.

    Args:
        start_date: The first date to backfill (inclusive). Will backfill from this date up to today.
    """
    overall_start_time = time.time()

    # Always backfill up to today
    end_date = service_date(datetime.datetime.now(EASTERN_TIME))

    # Validate date range
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) cannot be in the future (today is {end_date})")

    logger.info(f"Beginning backfill of events from {start_date} to {end_date}")

    total_files_uploaded = 0
    current_date = start_date

    # Iterate through each date in the range
    while current_date <= end_date:
        date_start_time = time.time()

        # Get files for this specific date
        files_for_date = glob.glob(
            LOCAL_DATA_TEMPLATE.format(year=current_date.year, month=current_date.month, day=current_date.day)
        )

        # Upload them to s3, gzipped
        for fp in files_for_date:
            _compress_and_upload_file(fp)

        date_end_time = time.time()
        logger.info(
            f"Uploaded {len(files_for_date)} files for {current_date}, "
            f"took {date_end_time - date_start_time:.2f} seconds."
        )

        total_files_uploaded += len(files_for_date)
        current_date += datetime.timedelta(days=1)

    overall_end_time = time.time()
    logger.info(
        f"Backfill complete. Uploaded {total_files_uploaded} files total, "
        f"took {overall_end_time - overall_start_time:.2f} seconds."
    )


if __name__ == "__main__":
    logger = set_up_logging(__file__)

    parser = argparse.ArgumentParser(
        description="Upload MBTA events to S3. Run without arguments for daily upload, or with --start-date for backfill."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for backfill in format MM-DD-YYYY (e.g., 01-28-2026). Will backfill from this date to today.",
    )

    args = parser.parse_args()

    if args.start_date:
        # Parse the date string
        try:
            start_date = datetime.datetime.strptime(args.start_date, "%m-%d-%Y").date()
            backfill_events_to_s3(start_date)
        except ValueError:
            logger.error(f"Invalid date format: {args.start_date}. Expected format: MM-DD-YYYY (e.g., 01-28-2026)")
            raise
    else:
        # Normal daily upload
        upload_todays_events_to_s3()
else:
    logger = set_up_logging(__name__)
