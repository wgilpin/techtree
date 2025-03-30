"""Utilities for interacting with the LLM, including retry logic and JSON parsing."""
# pylint: disable=broad-exception-caught

import os
import re
import time
import random
import json
from typing import Callable, Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from dotenv import load_dotenv

from backend.logger import logger

# Load environment variables
load_dotenv()

# Define MODEL type hint before assignment
MODEL: Optional[genai.GenerativeModel] = None # type: ignore[name-defined]

# Configure Gemini API (Consider moving this configuration elsewhere if used broadly)
# For now, keep it here as this module is the primary LLM interface
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gemini_model_name = os.environ.get("GEMINI_MODEL")
    if not gemini_api_key:
        logger.error("Missing environment variable: GEMINI_API_KEY")
        raise KeyError("GEMINI_API_KEY")
    if not gemini_model_name:
        logger.error("Missing environment variable: GEMINI_MODEL")
        raise KeyError("GEMINI_MODEL")

    genai.configure(api_key=gemini_api_key) # type: ignore[attr-defined]
    MODEL = genai.GenerativeModel(gemini_model_name) # type: ignore[attr-defined]
    logger.info(f"Gemini model '{gemini_model_name}' configured successfully.")

except KeyError as e:
    logger.error(f"Gemini configuration failed due to missing environment variable: {e}")
    MODEL = None # This assignment is now compatible with the type hint
except Exception as e:
    logger.error(f"An unexpected error occurred during Gemini configuration: {e}", exc_info=True)
    MODEL = None


# Define a TypeVar for Pydantic models
T = TypeVar("T", bound=BaseModel)


# Added type parameters to Callable
def call_with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    **kwargs: Any,
) -> Any:
    """
    Calls a function with exponential backoff retry logic, specifically for
    ResourceExhausted errors (like API quota limits).

    Args:
        func: The function to call.
        *args: Positional arguments for the function.
        max_retries: Maximum number of retries.
        initial_delay: Initial delay in seconds before the first retry.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function call.

    Raises:
        ResourceExhausted: If the maximum number of retries is exceeded.
        Exception: Any other exception raised by the function.
    """
    retries = 0
    delay = initial_delay
    while True:
        try:
            return func(*args, **kwargs)
        except ResourceExhausted as e:
            retries += 1
            if retries > max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__}."
                    " Raising ResourceExhausted."
                )
                raise e

            # Calculate delay with exponential backoff and jitter
            current_delay = delay * (2 ** (retries - 1)) + random.uniform(
                0, 0.5
            )
            logger.warning(
                f"ResourceExhausted error calling {func.__name__}."
                f" Retrying in {current_delay:.2f} seconds... (Attempt {retries}/{max_retries})"
            )
            time.sleep(current_delay)
        except Exception as e:
            logger.error(
                f"Non-retryable error calling {func.__name__}: {e}", exc_info=True
            )
            raise e


def call_llm_with_json_parsing(
    prompt: str,
    validation_model: Optional[Type[T]] = None,
    max_retries: int = 5,
    initial_delay: float = 1.0,
) -> Optional[T | Dict[str, Any]]:
    """
    Calls the configured LLM, attempts to parse a JSON object from the response,
    and optionally validates it against a Pydantic model.

    Args:
        prompt: The prompt string to send to the LLM.
        validation_model: Optional Pydantic model class to validate the JSON against.
        max_retries: Maximum retries for the LLM call (for quota errors).
        initial_delay: Initial delay for retries.

    Returns:
        - If validation_model is provided: An instance of the Pydantic model if
          parsing and validation are successful, otherwise None.
        - If validation_model is None: The parsed JSON dictionary if parsing is
          successful, otherwise None.
        - Returns None if the LLM call fails after retries or if JSON parsing fails.
    """
    if MODEL is None:
        logger.error("LLM MODEL not configured. Cannot make API call.")
        return None

    try:
        # Use call_with_retry for the actual API call
        response = call_with_retry(
            MODEL.generate_content,
            prompt,
            max_retries=max_retries,
            initial_delay=initial_delay,
        )
        response_text = response.text
        logger.debug(
            f"Raw LLM response: {response_text[:500]}..."
        )

    except ResourceExhausted:
        logger.error(
            "LLM call failed after multiple retries due to resource exhaustion."
        )
        return None
    except Exception as e:
        logger.error(f"LLM call failed with unexpected error: {e}", exc_info=True)
        return None

    # Attempt to extract JSON from the response text
    json_patterns = [
        r"```(?:json)?\s*({.*?})```",
        r"({[\s\S]*})",
    ]
    # Explicitly type parsed_json
    parsed_json: Optional[Dict[str, Any]] = None
    json_str_cleaned = None

    for pattern in json_patterns:
        json_match = re.search(pattern, response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            json_str_cleaned = re.sub(r"\\n", " ", json_str)
            try:
                # json.loads returns Any, cast it for safety
                loaded_data = json.loads(json_str_cleaned)
                if isinstance(loaded_data, dict):
                    parsed_json = loaded_data
                    logger.debug(f"Successfully parsed JSON using pattern: {pattern}")
                    break
                else:
                    logger.warning(f"Parsed JSON is not a dictionary: {type(loaded_data)}")
                    parsed_json = None # Reset if not a dict
            except json.JSONDecodeError as e:
                logger.warning(
                    f"JSON parsing failed for pattern {pattern} with "
                    f"cleaned string: {e}. String: '{json_str_cleaned[:100]}...'"
                )
                continue

    if parsed_json is None:
        logger.error(
            f"Failed to parse JSON from LLM response. Raw text: {response_text[:500]}..."
        )
        return None

    # Optional Pydantic validation
    if validation_model:
        try:
            validated_data = validation_model.model_validate(parsed_json)
            logger.debug(
                f"Successfully validated JSON against model: {validation_model.__name__}"
            )
            return validated_data # Returns type T
        except ValidationError as e:
            logger.error(
                f"Pydantic validation failed for model {validation_model.__name__}:"
                f" {e}. Parsed JSON: {parsed_json}"
            )
            return None
    else:
        # Return the raw parsed dictionary if no validation model is provided
        return parsed_json # Returns Dict[str, Any]


def call_llm_plain_text(
    prompt: str, max_retries: int = 3, initial_delay: float = 1.0
) -> Optional[str]:
    """
    Calls the configured LLM and returns the plain text response.

    Args:
        prompt: The prompt string to send to the LLM.
        max_retries: Maximum retries for the LLM call (for quota errors).
        initial_delay: Initial delay for retries.

    Returns:
        The plain text response string from the LLM, or None if the call fails
        after retries.
    """
    if MODEL is None:
        logger.error("LLM MODEL not configured. Cannot make API call.")
        return None

    try:
        # Use call_with_retry for the actual API call
        response = call_with_retry(
            MODEL.generate_content,
            prompt,
            max_retries=max_retries,
            initial_delay=initial_delay,
        )
        response_text = response.text
        logger.debug(
            f"Raw LLM response (plain text): {response_text[:500]}..."
        )
        # Ensure response_text is actually a string before returning
        return response_text if isinstance(response_text, str) else None

    except ResourceExhausted:
        logger.error(
            "LLM call failed after multiple retries due to resource exhaustion."
        )
        return None
    except Exception as e:
        logger.error(f"LLM call failed with unexpected error: {e}", exc_info=True)
        return None


# Example Usage / Simple Test Block
if __name__ == "__main__":
    #Runs simple tests when the script is executed directly.

    class SimpleResult(BaseModel):
        """A simple Pydantic model for testing validation."""
        status: str
        message: Optional[str] = None

    TEST_PROMPT_VALID = """
        Respond with ONLY the following JSON: {"status": "success", "message": "It worked!"}"""
    TEST_PROMPT_INVALID_JSON = """
        Respond with ONLY the following: {"status": "fail", message: "Invalid JSON"}"""
    TEST_PROMPT_INVALID_MODEL = (
        'Respond with ONLY the following JSON: {"status_code": 200}'
    )
    TEST_PROMPT_PLAIN = "Explain the concept of recursion in one sentence."


    print("\n--- Testing call_llm_with_json_parsing ---")

    # Test 1: Valid JSON, Valid Model
    print("\nTest 1: Valid JSON, Valid Model")
    result1 = call_llm_with_json_parsing(
        TEST_PROMPT_VALID, validation_model=SimpleResult
    )
    if result1:
        print(f"Result: {result1}")
        print(f"Is instance of SimpleResult: {isinstance(result1, SimpleResult)}")
    else:
        print("Failed.")

    # Test 2: Invalid JSON
    print("\nTest 2: Invalid JSON")
    result2 = call_llm_with_json_parsing(
        TEST_PROMPT_INVALID_JSON, validation_model=SimpleResult
    )
    if result2:
        print(f"Result: {result2}")
    else:
        print("Failed as expected.")

    # Test 3: Valid JSON, Invalid Model
    print("\nTest 3: Valid JSON, Invalid Model")
    result3 = call_llm_with_json_parsing(
        TEST_PROMPT_INVALID_MODEL, validation_model=SimpleResult
    )
    if result3:
        print(f"Result: {result3}")
    else:
        print("Failed as expected.")

    # Test 4: Valid JSON, No Model
    print("\nTest 4: Valid JSON, No Model")
    result4 = call_llm_with_json_parsing(TEST_PROMPT_VALID)
    if result4:
        print(f"Result: {result4}")
        print(f"Is dictionary: {isinstance(result4, dict)}")
    else:
        print("Failed.")

    print("\n--- Testing call_llm_plain_text ---")
    # Test 5: Plain text call
    print("\nTest 5: Plain Text Call")
    result5 = call_llm_plain_text(TEST_PROMPT_PLAIN)
    if result5:
        print(f"Result: {result5}")
        print(f"Is string: {isinstance(result5, str)}")
    else:
        print("Failed.")
