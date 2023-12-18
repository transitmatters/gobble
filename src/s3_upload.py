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

logging.basicConfig(level=logging.INFO)
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

s3 = boto3.client("s3")

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "*/Year={year}/Month={month}/Day={day}/events.csv")
S3_DATA_TEMPLATE = "Events-live/daily-bus-data/{relative_path}.gz"


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
    """Upload today's events to the TM s3 bucket.

    This is assumed to run on a 30 minute schedule, and as such we start the job from 45 minutes prior
    TODO: This process will work just as well for busses and CR, just need to update the local data/S3 key accordingly
    """
    start_time = time.time()

    print("Beginning upload of recent events to s3.")
    fortyfive_min_ago = datetime.datetime.now() - datetime.timedelta(minutes=45)

    # get files updated today
    # TODO: only update modified files? cant imagine much of a difference at 30 min update intervals...
    files_updated_today = glob.glob(
        LOCAL_DATA_TEMPLATE.format(
            year=fortyfive_min_ago.year, month=fortyfive_min_ago.month, day=fortyfive_min_ago.day
        )
    )

    # upload them to s3, gzipped
    for fp in files_updated_today:
        _compress_and_upload_file(fp)

    end_time = time.time()
    print(f"Uploaded {len(files_updated_today)} files to s3, took {end_time - start_time} seconds.")


if __name__ == "__main__":
    logger = logging.getLogger(__file__)
    upload_todays_events_to_s3()
else:
    logger = logging.getLogger(__name__)
