import datetime
import glob
import boto3
from disk import DATA_DIR
from io import BytesIO
import gzip
import os
import time
from ddtrace import tracer
import logging

from config import CONFIG
from util import EASTERN_TIME, service_date

logging.basicConfig(level=logging.INFO)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

s3 = boto3.client("s3")

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "daily*/*/Year={year}/Month={month}/Day={day}/events.csv")
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


@tracer.wrap("gobble")
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


if __name__ == "__main__":
    logger = logging.getLogger(__file__)
    upload_todays_events_to_s3()
else:
    logger = logging.getLogger(__name__)
