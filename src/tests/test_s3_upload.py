from unittest.mock import patch, mock_open
import datetime
import gzip
from pathlib import Path
from io import BytesIO
import pytest

import s3_upload
from util import EASTERN_TIME


class TestCompressAndUploadFile:
    """Test _compress_and_upload_file function"""

    @patch("s3_upload.s3")
    @patch("builtins.open", new_callable=mock_open, read_data=b"test,csv,data\n1,2,3\n")
    def test_compress_and_upload_file_basic(self, mock_file, mock_s3_client):
        """Test basic file compression and upload"""
        test_file_path = str(
            Path("data/daily-rapid/Red-0/Year=2024/Month=1/Day=15/events.csv")
        )

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
    @patch(
        "builtins.open", new_callable=mock_open, read_data=b"route,stop\nRed,Harvard\n"
    )
    def test_compress_and_upload_file_correct_s3_path(self, mock_file, mock_s3_client):
        """Test that S3 path is constructed correctly from file path"""
        test_file_path = "data/daily-bus/1-0/Year=2024/Month=3/Day=20/events.csv"

        s3_upload._compress_and_upload_file(test_file_path)

        # Get the S3 key that was used
        call_args = mock_s3_client.upload_fileobj.call_args
        s3_key = call_args[1]["Key"]

        # Should be Events-live/{relative_path}.gz
        expected_key = (
            "Events-live/daily-bus/1-0/Year=2024/Month=3/Day=20/events.csv.gz"
        )
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
    """Test upload_todays_events_to_s3 function"""

    @patch("s3_upload._compress_and_upload_file")
    @patch("s3_upload.glob.glob")
    @patch("s3_upload.service_date")
    @patch("s3_upload.datetime")
    def test_upload_todays_events_basic(
        self, mock_datetime, mock_service_date, mock_glob, mock_compress_and_upload
    ):
        """Test basic upload of today's events"""
        # Mock current time
        mock_now = datetime.datetime(2024, 1, 15, 14, 30, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock service date
        mock_service_date.return_value = datetime.date(2024, 1, 15)

        # Mock glob to return some files
        test_files = [
            "data/daily-rapid/Red-0/Year=2024/Month=1/Day=15/events.csv",
            "data/daily-rapid/Red-1/Year=2024/Month=1/Day=15/events.csv",
            "data/daily-bus/1-0/Year=2024/Month=1/Day=15/events.csv",
        ]
        mock_glob.return_value = test_files

        s3_upload.upload_todays_events_to_s3()

        # Verify service_date was called with current time
        mock_service_date.assert_called_once_with(mock_now)

        # Verify glob was called with correct pattern
        mock_glob.assert_called_once()
        glob_pattern = mock_glob.call_args[0][0]
        assert "Year=2024" in glob_pattern
        assert "Month=1" in glob_pattern
        assert "Day=15" in glob_pattern

        # Verify each file was uploaded
        assert mock_compress_and_upload.call_count == 3
        for test_file in test_files:
            mock_compress_and_upload.assert_any_call(test_file)

    @patch("s3_upload._compress_and_upload_file")
    @patch("s3_upload.glob.glob")
    @patch("s3_upload.service_date")
    @patch("s3_upload.datetime")
    def test_upload_todays_events_no_files(
        self, mock_datetime, mock_service_date, mock_glob, mock_compress_and_upload
    ):
        """Test upload when no files exist for today"""
        # Mock current time
        mock_now = datetime.datetime(2024, 1, 15, 14, 30, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock service date
        mock_service_date.return_value = datetime.date(2024, 1, 15)

        # Mock glob to return empty list
        mock_glob.return_value = []

        s3_upload.upload_todays_events_to_s3()

        # Should not attempt any uploads
        mock_compress_and_upload.assert_not_called()

    @patch("s3_upload._compress_and_upload_file")
    @patch("s3_upload.glob.glob")
    @patch("s3_upload.service_date")
    @patch("s3_upload.datetime")
    def test_upload_todays_events_overnight_service(
        self, mock_datetime, mock_service_date, mock_glob, mock_compress_and_upload
    ):
        """Test upload during overnight service (after midnight but still previous service day)"""
        # Mock current time - 2 AM (after midnight)
        mock_now = datetime.datetime(2024, 1, 16, 2, 0, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now

        # service_date should return previous day for overnight service
        mock_service_date.return_value = datetime.date(2024, 1, 15)

        # Mock glob to return files from previous service day
        test_files = ["data/daily-rapid/Red-0/Year=2024/Month=1/Day=15/events.csv"]
        mock_glob.return_value = test_files

        s3_upload.upload_todays_events_to_s3()

        # Verify glob used the service date (not calendar date)
        glob_pattern = mock_glob.call_args[0][0]
        assert "Year=2024" in glob_pattern
        assert "Month=1" in glob_pattern
        assert "Day=15" in glob_pattern  # Service day, not calendar day (16)

        # Verify upload was called
        mock_compress_and_upload.assert_called_once_with(test_files[0])

    @patch(
        "s3_upload._compress_and_upload_file", side_effect=Exception("S3 upload failed")
    )
    @patch("s3_upload.glob.glob")
    @patch("s3_upload.service_date")
    @patch("s3_upload.datetime")
    def test_upload_todays_events_upload_failure(
        self, mock_datetime, mock_service_date, mock_glob, mock_compress_and_upload
    ):
        """Test that upload failure raises exception"""
        # Mock current time
        mock_now = datetime.datetime(2024, 1, 15, 14, 30, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock service date
        mock_service_date.return_value = datetime.date(2024, 1, 15)

        # Mock glob to return one file
        mock_glob.return_value = [
            "data/daily-rapid/Red-0/Year=2024/Month=1/Day=15/events.csv"
        ]

        # Should raise the exception from compress_and_upload
        with pytest.raises(Exception) as context:
            s3_upload.upload_todays_events_to_s3()

        assert "S3 upload failed" in str(context.value)

    @patch("s3_upload._compress_and_upload_file")
    @patch("s3_upload.glob.glob")
    @patch("s3_upload.service_date")
    @patch("s3_upload.datetime")
    def test_upload_todays_events_multiple_routes(
        self, mock_datetime, mock_service_date, mock_glob, mock_compress_and_upload
    ):
        """Test upload with files from multiple routes and directions"""
        # Mock current time
        mock_now = datetime.datetime(2024, 6, 20, 10, 0, 0, tzinfo=EASTERN_TIME)
        mock_datetime.datetime.now.return_value = mock_now

        # Mock service date
        mock_service_date.return_value = datetime.date(2024, 6, 20)

        # Mock glob to return files from various routes
        test_files = [
            "data/daily-rapid/Red-0/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-rapid/Red-1/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-rapid/Orange-0/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-rapid/Orange-1/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-rapid/Blue-0/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-bus/1-0/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-bus/28-1/Year=2024/Month=6/Day=20/events.csv",
            "data/daily-cr/CR-Fitchburg-0/Year=2024/Month=6/Day=20/events.csv",
        ]
        mock_glob.return_value = test_files

        s3_upload.upload_todays_events_to_s3()

        # Verify all 8 files were uploaded
        assert mock_compress_and_upload.call_count == 8
        for test_file in test_files:
            mock_compress_and_upload.assert_any_call(test_file)


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



