from functools import wraps
from time import time
from random import random
import numpy as np


def measure_time(report_frequency: float = 1.0, trail_length=1000):
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
