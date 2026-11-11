from unittest.mock import patch, mock_open
import datetime
import gzip
import json
import os
import time
from pathlib import Path
from io import BytesIO
import pytest
from botocore.exceptions import ClientError

import s3_upload
from util import EASTERN_TIME


class TestCompressAndUploadFile:
    """Test _compress_and_upload_file function"""

    @patch("s3_upload.s3")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test,csv,data\n1,2,3\n")
    def test_compress_and_upload_file_basic(self, mock_file, mock_s3_client):
        """Test basic file compression and upload"""
        test_file_path = str(Path("data/daily-rapid/Red-0/Year=2024/Month=1/Day=15/events.csv"))

        s3_upload._compress_and_upload_file(test_file_path)

        # Verify file was opened for reading in binary mode
        mock_file.assert_called_once_with(test_file_path, "rb")

        # Verify s3 upload was called
        mock_s3_client.upload_fileobj.assert_called_once()

        # Check upload arguments
        call_args = mock_s3_client.upload_fileobj.call_args
        buffer_arg = call_args[0][0]
        bucket_arg = call_args[0][1]

        # Verify bucket name
        assert bucket_arg == "tm-mbta-performance"

        # Verify S3 key format
        assert "Key" in call_args[1]
        s3_key = call_args[1]["Key"]
        assert s3_key.startswith("Events-live/")
        assert s3_key.endswith(".gz")

        # Verify extra args for content type
        assert call_args[1]["ExtraArgs"]["ContentType"] == "text/csv"
        assert call_args[1]["ExtraArgs"]["ContentEncoding"] == "gzip"

        # Verify buffer contains gzipped data
        assert isinstance(buffer_arg, BytesIO)
        buffer_arg.seek(0)
        compressed_data = buffer_arg.read()
        decompressed = gzip.decompress(compressed_data)
        assert decompressed == b"test,csv,data\n1,2,3\n"

    @patch("s3_upload.s3")
    @patch("s3_upload.DATA_DIR", Path("data"))
    @patch("builtins.open", new_callable=mock_open, read_data=b"route,stop\nRed,Harvard\n")
    def test_compress_and_upload_file_correct_s3_path(self, mock_file, mock_s3_client):
        """Test that S3 path is constructed correctly from file path"""
        test_file_path = "data/daily-bus/1-0/Year=2024/Month=3/Day=20/events.csv"

        s3_upload._compress_and_upload_file(test_file_path)

        # Get the S3 key that was used
        call_args = mock_s3_client.upload_fileobj.call_args
        s3_key = call_args[1]["Key"]

        # Should be Events-live/{relative_path}.gz
        expected_key = "Events-live/daily-bus/1-0/Year=2024/Month=3/Day=20/events.csv.gz"
        assert s3_key == expected_key

    @patch("s3_upload.s3")
    @patch("builtins.open", new_callable=mock_open, read_data=b"")
    def test_compress_and_upload_empty_file(self, mock_file, mock_s3_client):
        """Test uploading an empty file"""
        test_file_path = "data/daily-rapid/Orange-1/Year=2024/Month=1/Day=1/events.csv"

        s3_upload._compress_and_upload_file(test_file_path)

        # Should still upload even if empty
        mock_s3_client.upload_fileobj.assert_called_once()

        # Verify empty compressed data
        call_args = mock_s3_client.upload_fileobj.call_args
        buffer_arg = call_args[0][0]
        buffer_arg.seek(0)
        compressed_data = buffer_arg.read()
        decompressed = gzip.decompress(compressed_data)
        assert decompressed == b""

    @patch("s3_upload.s3")
    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_compress_and_upload_file_not_found(self, mock_file, mock_s3_client):
        """Test error handling when file doesn't exist"""
        test_file_path = "data/nonexistent/file.csv"

        with pytest.raises(FileNotFoundError):
            s3_upload._compress_and_upload_file(test_file_path)

        # Should not attempt upload if file read fails
        mock_s3_client.upload_fileobj.assert_not_called()


class TestUploadTodaysEventsToS3:
    """Test upload_todays_events_to_s3 against a temporary data directory"""

    TODAY = datetime.date(2024, 1, 15)
    YESTERDAY = datetime.date(2024, 1, 14)

    @pytest.fixture
    def data_dir(self, tmp_path):
        with (
            patch(
                "s3_upload.LOCAL_DATA_TEMPLATE",
                str(tmp_path / "daily-*/*/Year={year}/Month={month}/Day={day}/events.csv"),
            ),
            patch("s3_upload.UPLOAD_STATE_PATH", tmp_path / "s3_upload_state.json"),
            patch("s3_upload.service_date", return_value=self.TODAY),
        ):
            yield tmp_path

    @pytest.fixture
    def upload(self):
        with patch("s3_upload._compress_and_upload_file") as mock_upload:
            yield mock_upload

    @pytest.fixture
    def cleanup(self):
        with (
            patch("s3_upload.cleanup_old_files") as mock_cleanup_files,
            patch("s3_upload.cleanup_old_gtfs_archives") as mock_cleanup_gtfs,
        ):
            yield mock_cleanup_files, mock_cleanup_gtfs

    @staticmethod
    def make_file(data_dir: Path, date: datetime.date, stop: str, age_seconds: float) -> str:
        path = data_dir / "daily-bus-data" / stop / f"Year={date.year}" / f"Month={date.month}" / f"Day={date.day}"
        path.mkdir(parents=True)
        fp = path / "events.csv"
        fp.write_text("service_date,route_id\n")
        mtime = time.time() - age_seconds
        os.utime(fp, (mtime, mtime))
        return str(fp)

    @staticmethod
    def uploaded(upload) -> set:
        return {call.args[0] for call in upload.call_args_list}

    @staticmethod
    def write_state(data_dir: Path, state: dict):
        (data_dir / "s3_upload_state.json").write_text(json.dumps(state))

    @staticmethod
    def read_state(data_dir: Path) -> dict:
        return json.loads((data_dir / "s3_upload_state.json").read_text())

    def test_first_run_uploads_everything_for_both_service_dates(self, data_dir, upload, cleanup):
        today = self.make_file(data_dir, self.TODAY, "1-0-64", age_seconds=3 * 3600)
        yesterday = self.make_file(data_dir, self.YESTERDAY, "1-0-64", age_seconds=24 * 3600)
        self.make_file(data_dir, datetime.date(2024, 1, 13), "1-0-64", age_seconds=48 * 3600)
        before = time.time()

        s3_upload.upload_todays_events_to_s3()

        assert self.uploaded(upload) == {today, yesterday}
        assert before <= self.read_state(data_dir)["last_uploaded_at"] <= time.time()

    def test_only_files_changed_since_last_run_are_uploaded(self, data_dir, upload, cleanup):
        self.write_state(data_dir, {"last_uploaded_at": time.time() - 1800, "last_cleanup_service_date": "2024-01-15"})
        self.make_file(data_dir, self.TODAY, "1-0-64", age_seconds=3600)
        changed = self.make_file(data_dir, self.TODAY, "1-0-2", age_seconds=60)
        # Modified just before the last run started, inside the safety margin
        in_margin = self.make_file(data_dir, self.TODAY, "1-0-3", age_seconds=1800 + 60)

        s3_upload.upload_todays_events_to_s3()

        assert self.uploaded(upload) == {changed, in_margin}

    def test_late_events_for_previous_service_date_are_uploaded(self, data_dir, upload, cleanup):
        """Events written between the 02:30 run and the 03:00 rollover belong to the previous service date"""
        self.write_state(data_dir, {"last_uploaded_at": time.time() - 1800, "last_cleanup_service_date": "2024-01-15"})
        late = self.make_file(data_dir, self.YESTERDAY, "111-0-5629", age_seconds=10 * 60)
        self.make_file(data_dir, self.YESTERDAY, "111-0-5620", age_seconds=3600)

        s3_upload.upload_todays_events_to_s3()

        assert self.uploaded(upload) == {late}

    def test_failed_upload_keeps_marker_so_files_are_retried(self, data_dir, upload, cleanup):
        last_uploaded_at = time.time() - 1800
        self.write_state(data_dir, {"last_uploaded_at": last_uploaded_at, "last_cleanup_service_date": "2024-01-15"})
        fp = self.make_file(data_dir, self.TODAY, "1-0-64", age_seconds=60)
        upload.side_effect = Exception("S3 upload failed")

        with pytest.raises(Exception, match="S3 upload failed"):
            s3_upload.upload_todays_events_to_s3()

        assert self.read_state(data_dir)["last_uploaded_at"] == last_uploaded_at

        upload.reset_mock(side_effect=True)
        s3_upload.upload_todays_events_to_s3()
        assert self.uploaded(upload) == {fp}

    @pytest.mark.parametrize("contents", ["{not json", "[]", '{"last_uploaded_at": "yesterday"}'])
    def test_unreadable_state_uploads_everything(self, data_dir, upload, cleanup, contents):
        (data_dir / "s3_upload_state.json").write_text(contents)
        old = self.make_file(data_dir, self.TODAY, "1-0-64", age_seconds=6 * 3600)

        s3_upload.upload_todays_events_to_s3()

        assert self.uploaded(upload) == {old}
        assert isinstance(self.read_state(data_dir)["last_uploaded_at"], float)

    def test_no_files(self, data_dir, upload, cleanup):
        s3_upload.upload_todays_events_to_s3()

        upload.assert_not_called()
        assert "last_uploaded_at" in self.read_state(data_dir)

    def test_cleanup_runs_once_per_service_date(self, data_dir, upload, cleanup):
        cleanup_files, cleanup_gtfs = cleanup

        s3_upload.upload_todays_events_to_s3()
        s3_upload.upload_todays_events_to_s3()
        assert cleanup_files.call_count == 1
        assert cleanup_gtfs.call_count == 1
        assert self.read_state(data_dir)["last_cleanup_service_date"] == "2024-01-15"

        with patch("s3_upload.service_date", return_value=datetime.date(2024, 1, 16)):
            s3_upload.upload_todays_events_to_s3()
        assert cleanup_files.call_count == 2
        assert cleanup_gtfs.call_count == 2
        assert self.read_state(data_dir)["last_cleanup_service_date"] == "2024-01-16"

    def test_failed_cleanup_is_retried_but_uploads_are_not(self, data_dir, upload, cleanup):
        cleanup_files, _ = cleanup
        cleanup_files.side_effect = OSError("disk error")
        fp = self.make_file(data_dir, self.TODAY, "1-0-64", age_seconds=3600)

        with pytest.raises(OSError):
            s3_upload.upload_todays_events_to_s3()
        assert self.uploaded(upload) == {fp}
        assert "last_cleanup_service_date" not in self.read_state(data_dir)

        upload.reset_mock()
        cleanup_files.side_effect = None
        s3_upload.upload_todays_events_to_s3()
        upload.assert_not_called()
        assert cleanup_files.call_count == 2

    @patch("s3_upload.datetime")
    def test_service_date_uses_eastern_time(self, mock_datetime, data_dir, upload, cleanup):
        mock_now = datetime.datetime(2024, 1, 16, 2, 0, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now
        mock_datetime.timedelta = datetime.timedelta

        s3_upload.upload_todays_events_to_s3()

        mock_datetime.datetime.now.assert_any_call(EASTERN_TIME)
        s3_upload.service_date.assert_called_once_with(mock_now)


class FakeS3:
    """Just enough of the S3 client for a restore: listing stop directories and getting gzipped objects"""

    def __init__(self, files: dict[str, str], last_modified: datetime.datetime):
        self.objects = {f"Events-live/{rp}.gz": gzip.compress(contents.encode()) for rp, contents in files.items()}
        self.last_modified = last_modified
        self.errors: dict[str, Exception] = {}

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, Bucket, Prefix, Delimiter):
        prefixes = sorted(
            {
                Prefix + key.removeprefix(Prefix).split(Delimiter)[0] + Delimiter
                for key in self.objects
                if key.startswith(Prefix)
            }
        )
        # One stop per page, then a page without CommonPrefixes, like the last page of an empty listing
        for prefix in prefixes:
            yield {"CommonPrefixes": [{"Prefix": prefix}]}
        yield {"KeyCount": 0}

    def get_object(self, Bucket, Key):
        if Key in self.errors:
            raise self.errors[Key]
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")
        return {"Body": BytesIO(self.objects[Key]), "LastModified": self.last_modified}


class TestRestoreRecentEventsFromS3:
    """Test restore_recent_events_from_s3 against a temporary data directory and a fake bucket"""

    TODAY = datetime.date(2024, 1, 15)
    YESTERDAY = datetime.date(2024, 1, 14)
    UPLOADED_AT = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

    @pytest.fixture
    def data_dir(self, tmp_path):
        with (
            patch("s3_upload.DATA_DIR", tmp_path),
            patch(
                "s3_upload.LOCAL_DATA_TEMPLATE",
                str(tmp_path / "daily-*/*/Year={year}/Month={month}/Day={day}/events.csv"),
            ),
            patch("s3_upload.UPLOAD_STATE_PATH", tmp_path / "s3_upload_state.json"),
            patch("s3_upload.service_date", return_value=self.TODAY),
            patch("s3_upload.CONFIG", {"modes": ["cr", "bus"]}),
        ):
            yield tmp_path

    @staticmethod
    def rp(mode: str, stop: str, date: datetime.date) -> str:
        return f"daily-{mode}-data/{stop}/Year={date.year}/Month={date.month}/Day={date.day}/events.csv"

    def bucket(self, files: dict[str, str]):
        """Returns a patch that swaps in a fake bucket holding these files, and the fake"""
        fake = FakeS3(files, self.UPLOADED_AT)
        return patch("s3_upload.s3", fake), fake

    def test_restores_both_service_dates_for_enabled_modes(self, data_dir):
        today = self.rp("bus", "1-0-64", self.TODAY)
        yesterday = self.rp("cr", "CR-Fairmount_0_DB-2205-01", self.YESTERDAY)
        older = self.rp("bus", "1-0-64", datetime.date(2024, 1, 13))
        # A stop with nothing for these dates, so its keys aren't in S3
        stale = self.rp("bus", "1-0-1", datetime.date(2023, 12, 14))
        disabled_mode = self.rp("rapid", "70061", self.TODAY)
        patched, _ = self.bucket(
            {today: "a\n1\n", yesterday: "a\n2\n", older: "a\n3\n", stale: "a\n4\n", disabled_mode: "a\n5\n"}
        )

        with patched:
            s3_upload.restore_recent_events_from_s3()

        assert (data_dir / today).read_text() == "a\n1\n"
        assert (data_dir / yesterday).read_text() == "a\n2\n"
        assert os.path.getmtime(data_dir / today) == self.UPLOADED_AT.timestamp()
        for not_restored in (older, stale, disabled_mode):
            assert not (data_dir / not_restored).exists()
        assert not list(data_dir.rglob("*.tmp"))

    def test_never_overwrites_a_local_file(self, data_dir):
        local = self.rp("bus", "1-0-64", self.TODAY)
        missing = self.rp("bus", "1-0-2", self.TODAY)
        (data_dir / local).parent.mkdir(parents=True)
        (data_dir / local).write_text("a\nlocal\n")
        patched, _ = self.bucket({local: "a\nfrom s3\n", missing: "a\nfrom s3\n"})

        with patched:
            s3_upload.restore_recent_events_from_s3()

        assert (data_dir / local).read_text() == "a\nlocal\n"
        assert (data_dir / missing).read_text() == "a\nfrom s3\n"
        # The local file may not be in S3 yet, so the next upload still uploads everything
        assert not (data_dir / "s3_upload_state.json").exists()

    def test_next_upload_only_sends_what_gobble_changes_after_a_restore(self, data_dir):
        appended = self.rp("bus", "1-0-64", self.TODAY)
        untouched = self.rp("bus", "1-0-2", self.TODAY)
        patched, _ = self.bucket({appended: "a\n1\n", untouched: "a\n2\n", self.rp("cr", "x", self.YESTERDAY): "a\n"})
        with patched:
            s3_upload.restore_recent_events_from_s3()

        # gobble appends to a restored file and starts a new one
        with open(data_dir / appended, "a") as f:
            f.write("3\n")
        new = self.rp("bus", "1-0-3", self.TODAY)
        (data_dir / new).parent.mkdir(parents=True)
        (data_dir / new).write_text("a\n4\n")

        with (
            patch("s3_upload._compress_and_upload_file") as upload,
            patch("s3_upload.cleanup_old_files"),
            patch("s3_upload.cleanup_old_gtfs_archives"),
        ):
            s3_upload.upload_todays_events_to_s3()

        assert {call.args[0] for call in upload.call_args_list} == {str(data_dir / appended), str(data_dir / new)}
        assert (data_dir / appended).read_text() == "a\n1\n3\n"

    def test_restores_the_rest_then_raises_when_a_download_fails(self, data_dir):
        failing = self.rp("bus", "1-0-64", self.TODAY)
        ok = self.rp("bus", "1-0-2", self.TODAY)
        patched, fake = self.bucket({failing: "a\n1\n", ok: "a\n2\n"})
        fake.errors[f"Events-live/{failing}.gz"] = ClientError({"Error": {"Code": "SlowDown"}}, "GetObject")
        before = time.time()

        with patched, pytest.raises(RuntimeError, match="Couldn't restore 1 of 4 files"):
            s3_upload.restore_recent_events_from_s3()

        assert not (data_dir / failing).exists()
        assert (data_dir / ok).read_text() == "a\n2\n"
        # The failed file isn't on disk, so advancing the marker can't make the next upload skip it
        state = json.loads((data_dir / "s3_upload_state.json").read_text())
        assert before <= state["last_uploaded_at"] <= time.time()

    def test_empty_bucket(self, data_dir):
        patched, _ = self.bucket({})

        with patched:
            s3_upload.restore_recent_events_from_s3()

        assert "last_uploaded_at" in json.loads((data_dir / "s3_upload_state.json").read_text())


class TestS3UploadConstants:
    """Test module constants"""

    def test_s3_bucket_name(self):
        """Verify S3 bucket name is correct"""
        assert s3_upload.S3_BUCKET == "tm-mbta-performance"

    def test_s3_data_template(self):
        """Verify S3 path template format"""
        assert s3_upload.S3_DATA_TEMPLATE == "Events-live/{relative_path}.gz"

    def test_local_data_template_has_wildcard_patterns(self):
        """Verify local data template has glob patterns"""
        template = s3_upload.LOCAL_DATA_TEMPLATE
        assert "daily-*" in template
        assert "Year=" in template
        assert "Month=" in template
        assert "Day=" in template
        assert "events.csv" in template
