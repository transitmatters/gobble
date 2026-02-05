"""S3 upload functionality for syncing event data to AWS.

This module handles uploading processed event data to the TransitMatters S3 bucket.
Files are compressed with gzip before upload to reduce storage costs and transfer time.

Attributes:
    S3_BUCKET: Name of the S3 bucket for storing event data.
    LOCAL_DATA_TEMPLATE: Glob pattern for finding local event files by date.
    S3_DATA_TEMPLATE: Template for generating S3 object keys from local paths.
"""

import datetime
import glob
import boto3
from io import BytesIO
import gzip
import os
import time
from ddtrace import tracer
import logging

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
    """Compress a local file with gzip and upload it to S3.

    Reads the file, compresses it in memory, and uploads to S3 with
    appropriate content headers for serving gzipped CSV data.

    Args:
        fp: Absolute path to the local file to upload.
    """
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
    """Upload all event files for today's service date to S3.

    Finds all CSV files matching today's service date across all routes
    and modes, compresses them, and uploads them to the TransitMatters
    S3 bucket. This function is typically run periodically to sync
    live data to the cloud.
    """
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


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    upload_todays_events_to_s3()
else:
    logger = set_up_logging(__name__)
