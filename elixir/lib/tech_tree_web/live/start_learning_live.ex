defmodule TechTreeWeb.StartLearningLive do
  use TechTreeWeb, :live_view

  alias TechTree.AI
  alias TechTree.Learning
  alias TechTree.Repo # Added
  alias Ecto.Multi # Added

  @impl true
  # import Phoenix.HTML.Form # Not needed when using TechTreeWeb, :live_view

  def mount(_params, _session, socket) do
    changeset = Ecto.Changeset.cast({%{}, %{topic: :string}}, %{topic: ""}, [:topic]) # Define :topic type
    form = to_form(changeset, as: :topic_input) # Add :as option

    {:ok,
     socket
     |> assign(:page_title, "Start Learning")
     |> assign(:form, form)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <.header>
      Choose a Topic
      <:subtitle>Enter a topic you want to learn about.</:subtitle>
    </.header>

    <div class="max-w-md mx-auto">
      <.simple_form for={@form} id="topic-form" phx-submit="generate_syllabus">
        <.input
          field={@form[:topic]}
          type="text"
          label="Topic"
          placeholder="e.g., Introduction to Quantum Computing"
          required
        />
        <:actions>
          <.button phx-disable-with="Generating...">Generate Syllabus</.button>
        </:actions>
      </.simple_form>
    </div>
    """
  end

  @impl true
  def handle_event("generate_syllabus", %{"topic_input" => %{"topic" => topic}}, socket) do # Update parameter matching
    # Disable button while generating
    socket = assign(socket, generating: true)

    case AI.generate_syllabus(topic) do
      {:ok, syllabus_attrs} ->
        # Use Learning context to create the syllabus and its nested parts
        case create_syllabus_from_ai(syllabus_attrs) do
          {:ok, syllabus} ->
            {:noreply,
             socket
             |> assign(:generating, false)
             |> put_flash(:info, "Syllabus '#{syllabus.topic}' generated successfully!")
             |> push_navigate(to: ~p"/syllabi/#{syllabus}")} # Navigate to the new syllabus page

          {:error, reason} ->
            {:noreply,
             socket
             |> assign(:generating, false)
             |> put_flash(:error, "Failed to save generated syllabus: #{inspect(reason)}")}
        end

      {:error, reason} ->
        {:noreply,
         socket
         |> assign(:generating, false)
         |> put_flash(:error, "Syllabus generation failed: #{inspect(reason)}")}
    end
  end

  # Helper function to create syllabus and nested modules/lessons
  defp create_syllabus_from_ai(attrs) do
    # Separate modules data from syllabus data
    modules_data = Map.get(attrs, "modules", [])
    syllabus_data = Map.drop(attrs, ["modules"])

    # Use a transaction to ensure all parts are created or none are
    Multi.new()
    |> Multi.insert(:syllabus, Learning.Syllabus.changeset(%Learning.Syllabus{}, syllabus_data))
    |> Multi.run(:modules, fn repo, %{syllabus: syllabus} ->
      create_modules_and_lessons(repo, syllabus, modules_data)
    end)
    |> Repo.transaction()
    |> case do
      {:ok, %{syllabus: syllabus}} -> {:ok, syllabus}
      {:error, _failed_operation, failed_value, _changes_so_far} ->
        {:error, failed_value} # Return the error changeset or reason
    end
  end

  defp create_modules_and_lessons(repo, syllabus, modules_data) do
    Enum.reduce_while(modules_data, {:ok, []}, fn module_data, {:ok, acc} ->
      lessons_data = Map.get(module_data, "lessons", [])
      module_attrs = Map.drop(module_data, ["lessons"]) |> Map.put("syllabus_id", syllabus.id)

      case Learning.create_module(module_attrs) do
        {:ok, module} ->
          case create_lessons(repo, module, lessons_data) do
            {:ok, _lessons} -> {:cont, {:ok, [module | acc]}}
            {:error, reason} -> {:halt, {:error, reason}} # Halt on lesson creation error
          end
        {:error, changeset} -> {:halt, {:error, changeset}} # Halt on module creation error
      end
    end)
  end

  defp create_lessons(_repo, module, lessons_data) do # Prefix unused repo with _
     Enum.reduce_while(lessons_data, {:ok, []}, fn lesson_attrs, {:ok, acc} ->
        attrs_with_id = Map.put(lesson_attrs, "module_id", module.id)
        case Learning.create_lesson(attrs_with_id) do
          {:ok, lesson} -> {:cont, {:ok, [lesson | acc]}}
          {:error, changeset} -> {:halt, {:error, changeset}} # Halt on lesson creation error
        end
     end)
  end
end
