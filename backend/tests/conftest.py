"""Pytest configuration file for backend tests.

Sets environment variables or performs other setup needed before tests run.
"""

import os

def pytest_configure(config):  # pylint: disable=unused-argument
    """Sets the RUNNING_TESTS environment variable before tests run."""
    os.environ["RUNNING_TESTS"] = "true"
    print("\npytest_configure: Set RUNNING_TESTS=true") # Added for confirmation