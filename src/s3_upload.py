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
    files_updated_today = glob.glob(
        LOCAL_DATA_TEMPLATE.format(year=pull_date.year, month=pull_date.month, day=pull_date.day)
    )

    # filter to only files modified in the last 2 hours to reduce S3 call costs
    current_time = time.time()
    two_hours_ago = current_time - (2 * 60 * 60)

    recently_modified_files = [
        fp for fp in files_updated_today
        if os.path.getmtime(fp) >= two_hours_ago
    ]

    # upload them to s3, gzipped
    for fp in recently_modified_files:
        _compress_and_upload_file(fp)

    end_time = time.time()
    logger.info(
        f"Uploaded {len(recently_modified_files)} files to s3 "
        f"({len(files_updated_today) - len(recently_modified_files)} skipped as not recently modified), "
        f"took {end_time - start_time} seconds."
    )


if __name__ == "__main__":
    logger = set_up_logging(__file__)
    upload_todays_events_to_s3()
else:
    logger = set_up_logging(__name__)
