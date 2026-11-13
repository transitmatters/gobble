import argparse
import datetime
import glob
import gzip
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from ddtrace import tracer

from config import CONFIG
from constants import ALL_MODES
from disk import CSV_FILENAME, DATA_DIR, cleanup_old_files
from gtfs import cleanup_old_gtfs_archives
from logger import set_up_logging
from util import EASTERN_TIME, service_date

logging.basicConfig(level=logging.INFO, filename="s3_upload.log")
tracer.enabled = CONFIG["DATADOG_TRACE_ENABLED"]

# A restore checks a few thousand keys, almost all of it waiting on S3, so it runs this many requests at once
RESTORE_WORKERS = 16

s3 = boto3.client("s3", config=Config(max_pool_connections=RESTORE_WORKERS))

S3_BUCKET = "tm-mbta-performance"

LOCAL_DATA_TEMPLATE = str(DATA_DIR / "daily-*/*/Year={year}/Month={month}/Day={day}/events.csv")
S3_DATA_PREFIX = "Events-live/"
S3_DATA_TEMPLATE = S3_DATA_PREFIX + "{relative_path}.gz"

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


def _list_stop_dirs(mode: str) -> list[str]:
    """Every stop directory in S3 for a mode, relative to DATA_DIR, e.g. daily-bus-data/1-0-64/"""
    pages = s3.get_paginator("list_objects_v2").paginate(
        Bucket=S3_BUCKET, Prefix=f"{S3_DATA_PREFIX}daily-{mode}-data/", Delimiter="/"
    )
    return [p["Prefix"].removeprefix(S3_DATA_PREFIX) for page in pages for p in page.get("CommonPrefixes", [])]


def _restore_file(relative_path: str) -> bool:
    """Download one event file from S3, unless it's already on disk or not in S3. Returns whether it was written."""
    local_path = DATA_DIR / relative_path
    if local_path.exists():
        return False
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_DATA_TEMPLATE.format(relative_path=relative_path))
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return False
        raise
    contents = gzip.decompress(obj["Body"].read())

    local_path.parent.mkdir(parents=True, exist_ok=True)
    # Rename into place, so an interrupted restore never leaves a partial file for gobble to append to
    tmp_path = local_path.with_name(f"{local_path.name}.tmp")
    tmp_path.write_bytes(contents)
    # Keep the upload time as the mtime, so the next upload knows S3 already has this version
    uploaded_at = obj["LastModified"].timestamp()
    os.utime(tmp_path, (uploaded_at, uploaded_at))
    os.replace(tmp_path, local_path)
    return True


@tracer.wrap(service="gobble")
def restore_recent_events_from_s3():
    """
    Download the current and previous service dates' event files from S3 that aren't on disk. Run this on a new
    instance before gobble first starts. Otherwise gobble starts those files over, and the next upload replaces
    everything already uploaded for the day with only the events written since. Never overwrites a local file.
    """
    start_time = time.time()
    pull_date = service_date(datetime.datetime.now(EASTERN_TIME))
    dates = [pull_date - datetime.timedelta(days=1), pull_date]
    had_local_files = any(_files_for_service_date(date) for date in dates)

    logger.info(f"Beginning restore of events for {dates[0]} and {dates[1]} from s3.")
    stop_dirs = [stop_dir for mode in CONFIG.get("modes", ALL_MODES) for stop_dir in _list_stop_dirs(mode)]
    relative_paths = [
        f"{stop_dir}Year={date.year}/Month={date.month}/Day={date.day}/{CSV_FILENAME}"
        for stop_dir in stop_dirs
        for date in dates
    ]

    restored = failed = 0
    with ThreadPoolExecutor(max_workers=RESTORE_WORKERS) as pool:
        futures = {pool.submit(_restore_file, rp): rp for rp in relative_paths}
        for future in as_completed(futures):
            try:
                restored += future.result()
            except Exception:
                failed += 1
                logger.exception(f"Couldn't restore {futures[future]} from s3")

    # Everything on disk for these dates now matches S3, so the next upload only needs the files gobble changes
    # from here on. Files that failed to download aren't on disk, so this doesn't skip them. If there were already
    # files, some may have changed since the last upload, so the marker is left alone.
    if not had_local_files:
        UPLOAD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = _read_upload_state()
        state["last_uploaded_at"] = start_time
        _write_upload_state(state)

    logger.info(
        f"Restored {restored} files from s3 ({len(stop_dirs)} stops checked for 2 service dates), "
        f"took {time.time() - start_time:.2f} seconds."
    )
    if failed:
        raise RuntimeError(f"Couldn't restore {failed} of {len(relative_paths)} files from s3")


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
        description="Upload MBTA events to S3. Run without arguments for daily upload, with --start-date for backfill, "
        "or with --restore to download recent events onto a new instance."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--start-date",
        type=str,
        help="Start date for backfill in format MM-DD-YYYY (e.g., 01-28-2026). Will backfill from this date to today.",
    )
    action.add_argument(
        "--restore",
        action="store_true",
        help="Download the current and previous service dates' events from S3 that aren't on disk. Run on a new "
        "instance before gobble first starts, so the next upload adds to the day's files instead of replacing them.",
    )

    args = parser.parse_args()

    if args.restore:
        restore_recent_events_from_s3()
    elif args.start_date:
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
