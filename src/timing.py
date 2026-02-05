"""Performance timing utilities for debugging and profiling.

This module provides decorators for measuring function execution time,
useful for identifying performance bottlenecks during development.
"""

from functools import wraps
from time import time
from random import random
import numpy as np


def measure_time(report_frequency: float = 1.0, trail_length: int = 1000):
    """Decorator factory for measuring and reporting function execution time.

    Creates a decorator that tracks execution times of the wrapped function
    and periodically prints statistics including last, min, max, average,
    and standard deviation of execution times.

    Args:
        report_frequency: Probability (0.0 to 1.0) of printing stats after
            each call. Defaults to 1.0 (always report).
        trail_length: Maximum number of recent execution times to keep for
            calculating statistics. Defaults to 1000.

    Returns:
        A decorator function that wraps the target function with timing logic.

    Example:
        >>> @measure_time(report_frequency=0.1)
        ... def slow_function():
        ...     time.sleep(1)
    """
    def decorator(fn):
        exec_times = []

        @wraps(fn)
        def wrap(*args, **kw):
            nonlocal exec_times
            ts = time()
            result = fn(*args, **kw)
            te = time()
            exec_times.append(te - ts)
            if random() < report_frequency:
                last = exec_times[-1]
                exec_times = exec_times[-trail_length:]
                avg = np.mean(exec_times)
                std = np.std(exec_times)
                min = np.min(exec_times)
                max = np.max(exec_times)
                print(f"func {fn.__name__}: last={last:.3f}s min={min:.3f} max={max:.3f} avg={avg:.3f}s std={std:.3f}s")
            return result

        return wrap

    return decorator
