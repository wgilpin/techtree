defmodule TechTree.AI do
  @moduledoc """
  The AI context, responsible for interactions with Large Language Models (LLMs).
  """
  # alias TechTree.Learning # Not used directly here yet

  # Google Gemini API details
  # Note: Ensure the region/project ID are correct if needed for the endpoint.
  @gemini_api_base_url "https://generativelanguage.googleapis.com/v1beta/models"
  @gemini_model "gemini-2.0-flash" # Use the specified model

  @doc """
  Generates a syllabus for a given topic using the Google Gemini LLM.

  Returns `{:ok, syllabus_attrs}` or `{:error, reason}`.
  The `syllabus_attrs` map includes nested `modules` with nested `lessons`.
  """
  @spec generate_syllabus(String.t()) :: {:ok, map()} | {:error, any()}
  def generate_syllabus(topic) when is_binary(topic) do
    api_key = Application.fetch_env!(:tech_tree, :google_api_key)
    url = "#{@gemini_api_base_url}/#{@gemini_model}:generateContent?key=#{api_key}"

    # Gemini uses a different prompt structure and expects JSON directly in the prompt
    # for structured output, rather than a separate response_format parameter.
    prompt = """
    Generate a concise syllabus for the topic "#{topic}".
    The syllabus should be suitable for an adaptive learning platform providing bite-sized lessons.
    Assume a beginner level unless the topic implies otherwise.
    The output MUST be a valid JSON object with the following structure:
    ```json
    {
      "topic": "#{topic}",
      "level": "Beginner",
      "duration": "Self-paced",
      "learning_objectives": ["Objective 1", "Objective 2", ...],
      "modules": [
        {
          "title": "Module 1 Title",
          "lessons": [
            {"title": "Lesson 1.1 Title"},
            {"title": "Lesson 1.2 Title"}
          ]
        },
        {
          "title": "Module 2 Title",
          "lessons": [
            {"title": "Lesson 2.1 Title"}
          ]
        }
      ]
    }
    ```
    Only output the JSON object, with no surrounding text or markdown formatting.
    """

    # Gemini API request body structure
    body =
      %{
        contents: [%{parts: [%{text: prompt}]}],
        # Optional: Add generationConfig for temperature, safety settings etc.
        # generationConfig: %{
        #   temperature: 0.7,
        #   # Ensure JSON output - might need specific safety settings if model refuses
        #   response_mime_type: "application/json" # Check if model supports this directly
        # }
      }
      |> Jason.encode!()

    headers = [
      {"Content-Type", "application/json"}
    ]

    case Finch.build(:post, url, headers, body) |> Finch.request(TechTree.Finch) do
      {:ok, %{status: 200, body: resp_body}} ->
        parse_gemini_syllabus_response(resp_body)

      {:ok, %{status: status, body: resp_body}} ->
        {:error, "Gemini API request failed with status #{status}: #{resp_body}"}

      {:error, reason} ->
        {:error, "HTTP request failed: #{inspect(reason)}"}
    end
  end

  # Updated parser for Gemini's response structure
  defp parse_gemini_syllabus_response(resp_body) do
    case Jason.decode(resp_body) do
      {:ok, json} ->
        # Now use `with` just for extracting the content, `json` is available in `else`
        with [%{"content" => %{"parts" => [%{"text" => content}]}} | _] <- Map.get(json, "candidates") do
          # Attempt to decode the content directly
          case Jason.decode(content) do
            {:ok, syllabus_attrs} ->
              # Basic validation
              if Map.has_key?(syllabus_attrs, "topic") && Map.has_key?(syllabus_attrs, "modules") do
                {:ok, syllabus_attrs}
              else
                {:error, "Gemini response JSON missing required keys (topic, modules): #{content}"}
              end

            # If direct decoding fails, try stripping markdown
            {:error, _} ->
              stripped_content = String.trim(content, " \n\t\r") |> String.trim_leading("```json") |> String.trim_trailing("```")
              case Jason.decode(stripped_content) do
                {:ok, syllabus_attrs} ->
                  if Map.has_key?(syllabus_attrs, "topic") && Map.has_key?(syllabus_attrs, "modules") do
                    {:ok, syllabus_attrs}
                  else
                    {:error, "Gemini response JSON (stripped) missing required keys: #{stripped_content}"}
                  end
                {:error, _} ->
                  {:error, "Failed to decode syllabus JSON from Gemini response content (even after stripping): #{content}"}
              end
          end
        # Handle cases where the `with` pattern doesn't match (e.g., no candidates, wrong structure)
        else
          _ ->
            # Handle potential block reasons or other errors from the raw JSON
            block_reason = json |> Map.get("promptFeedback", %{}) |> Map.get("blockReason")
            error_details = if block_reason, do: " (Block Reason: #{block_reason})", else: ""
            {:error, "Failed to parse Gemini response structure#{error_details}: #{resp_body}"}
        end
      # Error decoding the initial response body
      {:error, _} ->
        {:error, "Failed to decode Gemini JSON response body: #{resp_body}"}
    end
  end
end
