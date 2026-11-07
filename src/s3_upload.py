import argparse
import datetime
import glob
import gzip
import json
import logging
import os
import time
from io import BytesIO

import boto3
from ddtrace import tracer

from config import CONFIG
from disk import DATA_DIR, cleanup_old_files
from gtfs import cleanup_old_gtfs_archives
from logger import set_up_logging
from util import EASTERN_TIME, service_date

logging.basicConfig(level=logging.INFO, filename="s3_upload.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

s3 = boto3.client("s3")

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "daily-*/*/Year={year}/Month={month}/Day={day}/events.csv")
S3_DATA_TEMPLATE = "Events-live/{relative_path}.gz"

# Remembers when the last fully successful upload run started, and the last service date old files were cleaned up
UPLOAD_STATE_PATH = DATA_DIR / "s3_upload_state.json"
# A file is re-uploaded if it was modified after this long before the last successful run started. The margin
# covers clock adjustments between runs; re-uploading a few unchanged files is harmless.
MTIME_MARGIN_SECONDS = 5 * 60


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


def _read_upload_state() -> dict:
    """Read the upload state file. Returns {} if it's missing or unreadable, which makes the run upload everything."""
    try:
        with open(UPLOAD_STATE_PATH) as f:
            state = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning(f"Ignoring unreadable {UPLOAD_STATE_PATH}: {e}")
        return {}
    return state if isinstance(state, dict) else {}


def _write_upload_state(state: dict):
    tmp_path = UPLOAD_STATE_PATH.with_name(f"{UPLOAD_STATE_PATH.name}.tmp")
    with open(tmp_path, "w") as f:
        json.dump(state, f)
    os.replace(tmp_path, UPLOAD_STATE_PATH)


def _files_for_service_date(date: datetime.date) -> list[str]:
    return glob.glob(LOCAL_DATA_TEMPLATE.format(year=date.year, month=date.month, day=date.day))


@tracer.wrap(service="gobble")
def upload_todays_events_to_s3():
    """Upload events written since the last successful run to the TM s3 bucket, then clean up once a day."""
    start_time = time.time()
    start_datetime = datetime.datetime.now()

    logger.info("Beginning upload of recent events to s3.")
    state = _read_upload_state()
    pull_date = service_date(datetime.datetime.now(EASTERN_TIME))

    # Include the previous service date: its last events are written after the run before the 03:00 rollover
    candidate_files = _files_for_service_date(pull_date - datetime.timedelta(days=1)) + _files_for_service_date(
        pull_date
    )

    last_uploaded_at = state.get("last_uploaded_at")
    if isinstance(last_uploaded_at, (int, float)):
        cutoff = last_uploaded_at - MTIME_MARGIN_SECONDS
        files_to_upload = [fp for fp in candidate_files if os.path.getmtime(fp) >= cutoff]
    else:
        # No record of a successful run, so upload everything for both service dates
        files_to_upload = candidate_files

    # upload them to s3, gzipped
    for fp in files_to_upload:
        _compress_and_upload_file(fp)

    # Only advance the marker once every upload succeeded, so a failed run's files are retried next time.
    # Files written while this run was reading have a later mtime than start_time and are picked up next run.
    state["last_uploaded_at"] = start_time
    _write_upload_state(state)

    end_time = time.time()
    logger.info(
        f"Uploaded {len(files_to_upload)} files to s3 ({len(candidate_files)} for the last two service dates), "
        f"took {end_time - start_time} seconds."
    )

    # cleanup old files and GTFS archives once per service date, free up disk space
    if state.get("last_cleanup_service_date") != pull_date.isoformat():
        cleanup_old_files(reference_time=start_datetime)
        cleanup_old_gtfs_archives(reference_time=start_datetime)
        state["last_cleanup_service_date"] = pull_date.isoformat()
        _write_upload_state(state)


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
