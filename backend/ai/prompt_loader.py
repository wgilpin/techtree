"""Utility for loading and formatting prompts from files."""

import os
from string import Template
from typing import Any

# Define the base directory for prompts relative to this file's location
# This assumes prompt_loader.py is in backend/ai/
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "lessons", "prompts")

class PromptTemplate(Template):
    """Custom Template subclass to allow partial formatting."""
    # Keep the default delimiter and idpattern
    # Override pattern if needed for more complex scenarios

def load_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Loads a prompt template from a file and substitutes placeholders.

    Args:
        prompt_name: The name of the prompt file (without extension).
        **kwargs: Keyword arguments representing placeholders and their values.

    Returns:
        The formatted prompt string.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        KeyError: If a placeholder in the template is not provided in kwargs.
    """
    file_path = os.path.join(PROMPT_DIR, f"{prompt_name}.prompt")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            template_content = f.read()
    except FileNotFoundError as ex:
        raise FileNotFoundError(f"Prompt file not found: {file_path}") from ex

    template = PromptTemplate(template_content)

    # Using safe_substitute to avoid errors if not all placeholders are needed
    # for a specific call, though ideally all required ones should be passed.
    # If strict checking is needed, use substitute() which raises KeyError.
    try:
        formatted_prompt = template.substitute(**kwargs)
        return formatted_prompt
    except KeyError as ex:
        raise KeyError(f"Missing placeholder value for '{ex}' in prompt '{prompt_name}'") from ex
    except Exception as ex:
        # Catch other potential formatting errors
        raise ValueError(f"Error formatting prompt '{prompt_name}': {ex}") from ex

# Example Usage (can be removed or kept for testing):
if __name__ == "__main__":
    try:
        # Example for intent classification
        history_example = [{"role": "user", "content": "Tell me more about Python."}]
        import json
        formatted = load_prompt(
            "intent_classification",
            history_json=json.dumps(history_example, indent=2),
            user_input="What is a decorator?",
        )
        print("--- Intent Classification Example ---")
        print(formatted)
        print("\n" + "="*20 + "\n")

        # Example for chat response
        formatted_chat = load_prompt(
            "chat_response",
            lesson_title="Python Basics",
            exposition="Python is a versatile language...",
            history_json=json.dumps(history_example[-1:], indent=2) # Only last message
        )
        print("--- Chat Response Example ---")
        print(formatted_chat)
        print("\n" + "="*20 + "\n")

        # Example for evaluation
        context_example_str = "Question: What is 2+2?\nExpected Answer: 4\nUser Answer: 4" # pylint: disable=invalid-name
        formatted_eval = load_prompt(
            "evaluate_answer",
            question_type="math question",
            prompt_context=context_example_str
        )
        print("--- Evaluation Example ---")
        print(formatted_eval)

    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"Error loading/formatting prompt: {e}")