defmodule TechTreeWeb.CourseModuleLive.FormComponent do # Renamed
  use TechTreeWeb, :live_component

  alias TechTree.Learning
  # alias TechTree.Learning.CourseModule # Not directly used here

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <.header>
        {@title}
        <:subtitle>Use this form to manage course module records in your database.</:subtitle> # Renamed
      </.header>

      <.simple_form
        for={@form}
        id="course-module-form"
        phx-target={@myself}
        phx-change="validate"
        phx-submit="save"
      >
        <.input field={@form[:title]} type="text" label="Title" />
        <.input field={@form[:syllabus_id]} type="number" label="Syllabus ID" /> # Added syllabus_id input
        <:actions>
          <.button phx-disable-with="Saving...">Save Course Module</.button> # Renamed
        </:actions>
      </.simple_form>
    </div>
    """
  end

  @impl true
  def update(%{course_module: current_module} = assigns, socket) do # Renamed received assign key
    {:ok,
     socket
     |> assign(assigns)
     |> assign_new(:form, fn ->
       to_form(Learning.change_module(current_module)) # Use renamed context function
     end)}
  end

  @impl true
  def handle_event("validate", %{"course_module" => module_params}, socket) do
    changeset = Learning.change_module(socket.assigns.current_module, module_params) # Use renamed context function
    {:noreply, assign(socket, form: to_form(changeset, action: :validate))}
  end

  def handle_event("save", %{"course_module" => module_params}, socket) do
    save_module(socket, socket.assigns.action, module_params)
  end

  defp save_module(socket, :edit, module_params) do # Uses socket.assigns.current_module
    case Learning.update_module(socket.assigns.current_module, module_params) do # Use renamed context function
      {:ok, course_module} -> # Renamed variable
        notify_parent({:saved, course_module}) # Renamed variable

        {:noreply,
         socket
         |> put_flash(:info, "Course Module updated successfully") # Renamed
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp save_module(socket, :new, module_params) do # Uses module_params directly
    case Learning.create_module(module_params) do # Use renamed context function
      {:ok, course_module} -> # Renamed variable
        notify_parent({:saved, course_module}) # Renamed variable

        {:noreply,
         socket
         |> put_flash(:info, "Course Module created successfully") # Renamed
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp notify_parent(msg), do: send(self(), {__MODULE__, msg})
end
