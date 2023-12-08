import datetime
import glob
import boto3
from disk import DATA_DIR
from io import BytesIO
import gzip
import os
import time

s3 = boto3.client("s3")

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "*/Year={year}/Month={month}/Day={day}/events.csv")
S3_DATA_TEMPLATE = "Events-live/daily-bus-data/{relative_path}.gz"


def _compress_and_upload(fp: str):
    """Compress a file in-memory and upload to S3."""
    # generate output location
    rp = os.path.relpath(fp, DATA_DIR)
    s3_key = S3_DATA_TEMPLATE.format(relative_path=rp)

    with open(fp, "rb") as f:
        # gzip to buffer and upload
        gz_bytes = gzip.compress(f.read())
        buffer = BytesIO(gz_bytes)

        s3.upload_fileobj(
            buffer, S3_BUCKET, Key=s3_key, ExtraArgs={"ContentType": "text/csv", "Content-Encoding": "gzip"}
        )


def main():
    start_time = time.time()

    print("Beginning upload of recent bus events to s3.")
    thirty_min_ago = datetime.datetime.now() - datetime.timedelta(minutes=30)

    # get files updated today
    # TODO: only update modified files? cant image much of a difference at 30 min intervals...
    files_updated_today = glob.glob(
        LOCAL_DATA_TEMPLATE.format(year=thirty_min_ago.year, month=thirty_min_ago.month, day=thirty_min_ago.day)
    )

    # upload them to s3, gzipped
    for fp in files_updated_today:
        _compress_and_upload(fp)

    end_time = time.time()
    print(f"Uploaded {len(files_updated_today)} to s3, took {end_time - start_time} seconds.")


if __name__ == "__main__":
    main()