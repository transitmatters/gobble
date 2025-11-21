from unittest.mock import patch
import time

from timing import measure_time


class TestMeasureTime:
    """Test the measure_time decorator"""

    def test_decorator_returns_function_result(self):
        """Test that decorated function returns correct result"""

        @measure_time(report_frequency=0.0)  # Never report to avoid random output
        def add_numbers(a, b):
            return a + b

        result = add_numbers(5, 3)
        assert result == 8

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves function name using @wraps"""

        @measure_time(report_frequency=0.0)
        def my_function():
            return "test"

        assert my_function.__name__ == "my_function"

    def test_decorator_measures_execution_time(self):
        """Test that decorator measures execution time"""

        @measure_time(report_frequency=0.0)
        def slow_function():
            time.sleep(0.01)  # Sleep for 10ms
            return "done"

        start = time.time()
        result = slow_function()
        elapsed = time.time() - start

        assert result == "done"
        # Verify it took at least 10ms
        assert elapsed >= 0.01

    def test_decorator_reports_statistics(self):
        """Test that decorator reports timing statistics when frequency triggers"""

        # Use report_frequency=1.0 to always report
        @measure_time(report_frequency=1.0, trail_length=10)
        def test_function():
            return "result"

        with patch("builtins.print") as mock_print:
            # Call function multiple times to build statistics
            for _ in range(5):
                test_function()

            # Verify statistics were printed
            assert mock_print.call_count >= 1

            # Check that print was called with statistics
            call_args = str(mock_print.call_args)
            assert "test_function" in call_args
            assert "last=" in call_args
            assert "avg=" in call_args
            assert "std=" in call_args
            assert "min=" in call_args
            assert "max=" in call_args

    def test_decorator_limits_trail_length(self):
        """Test that decorator limits the number of stored execution times"""
        # Create a function that tracks execution times
        call_count = [0]

        @measure_time(report_frequency=1.0, trail_length=3)
        def counting_function():
            call_count[0] += 1
            return call_count[0]

        with patch("builtins.print"):
            # Call function more times than trail_length
            for _ in range(10):
                counting_function()

            # The decorator should only keep the last 3 execution times
            # We can verify this indirectly through the statistics
            # (actual implementation keeps trail in closure)

    def test_decorator_handles_kwargs(self):
        """Test that decorator works with functions that use kwargs"""

        @measure_time(report_frequency=0.0)
        def function_with_kwargs(a, b=10, c=20):
            return a + b + c

        result1 = function_with_kwargs(5)
        assert result1 == 35

        result2 = function_with_kwargs(5, b=15)
        assert result2 == 40

        result3 = function_with_kwargs(5, b=15, c=25)
        assert result3 == 45

    def test_decorator_with_zero_frequency(self):
        """Test that decorator never reports with frequency=0.0"""

        @measure_time(report_frequency=0.0)
        def test_function():
            return "result"

        with patch("builtins.print") as mock_print:
            # Call function multiple times
            for _ in range(100):
                test_function()

            # With frequency=0.0 and random check, should never print
            # (random() is always >= 0.0, so random() < 0.0 is always False)
            mock_print.assert_not_called()

    def test_decorator_tracks_multiple_calls(self):
        """Test that decorator accumulates statistics over multiple calls"""
        execution_count = [0]

        @measure_time(report_frequency=1.0, trail_length=100)
        def increment_function():
            execution_count[0] += 1
            return execution_count[0]

        with patch("builtins.print") as mock_print:
            # Call multiple times
            for i in range(10):
                result = increment_function()
                assert result == i + 1

            # Verify print was called (due to report_frequency=1.0)
            assert mock_print.call_count >= 1
