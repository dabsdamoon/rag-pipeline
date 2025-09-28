"""Timing utilities shared across pipeline components."""

from __future__ import annotations

import functools
import time
from typing import Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable)


def measure_time(func_name: Optional[str] = None):
    """Decorator to log execution time for diagnostic purposes."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                name = func_name or func.__name__
                print(f"[TIMING] {name} took {execution_time:.4f} seconds")
                return result
            except Exception as exc:
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                name = func_name or func.__name__
                print(f"[TIMING] {name} failed after {execution_time:.4f} seconds: {exc}")
                raise

        return wrapper  # type: ignore[return-value]

    return decorator

