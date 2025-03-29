"""Utility functions for the syllabus generation module."""

import time
import random
from typing import Callable, Any # Added imports
from google.api_core.exceptions import ResourceExhausted

# Added type annotations
def call_with_retry(
    func: Callable[..., Any], # Type hint for the function
    *args: Any,               # Type hint for positional args
    max_retries: int = 5,
    initial_delay: float = 1.0, # Type hint for delay
    **kwargs: Any              # Type hint for keyword args
) -> Any:                      # Type hint for return value
    """Calls a function with exponential backoff retry logic for ResourceExhausted errors."""
    retries = 0
    delay = initial_delay # Use the typed initial_delay
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted:
            retries += 1
            if retries > max_retries:
                print(f"Max retries ({max_retries}) exceeded for {func.__name__}.")
                raise
            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
            print(
                f"ResourceExhausted error. Retrying {func.__name__} in "
                f"{current_delay:.2f} seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except Exception as e:
            # Catch other potential exceptions during the call
            print(f"Non-retryable error during {func.__name__} call: {e}")
            raise  # Re-raise other exceptions immediately
