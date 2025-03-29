"""Utility functions for the syllabus generation module."""

import time
import random
from google.api_core.exceptions import ResourceExhausted

def call_with_retry(func, *args, max_retries=5, initial_delay=1, **kwargs):
    """Calls a function with exponential backoff retry logic for ResourceExhausted errors."""
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                print(f"Max retries ({max_retries}) exceeded for {func.__name__}.")
                raise

            # Calculate delay with exponential backoff and jitter
            delay = initial_delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            print(
                f"ResourceExhausted error. Retrying {func.__name__} in "
                f"{delay:.2f} seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(delay)
        except Exception as e:
            # Catch other potential exceptions during the call
            print(f"Non-retryable error during {func.__name__} call: {e}")
            raise  # Re-raise other exceptions immediately
