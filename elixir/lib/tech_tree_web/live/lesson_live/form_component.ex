defmodule TechTreeWeb.LessonLive.FormComponent do
  use TechTreeWeb, :live_component

  alias TechTree.Learning

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <.header>
        {@title}
        <:subtitle>Use this form to manage lesson records in your database.</:subtitle>
      </.header>

      <.simple_form
        for={@form}
        id="lesson-form"
        phx-target={@myself}
        phx-change="validate"
        phx-submit="save"
      >
        <.input field={@form[:title]} type="text" label="Title" />
        <.input field={@form[:course_module_id]} type="number" label="Course Module ID" />
        <:actions>
          <.button phx-disable-with="Saving...">Save Lesson</.button>
        </:actions>
      </.simple_form>
    </div>
    """
  end

  @impl true
  def update(%{lesson: lesson} = assigns, socket) do
    {:ok,
     socket
     |> assign(assigns)
     |> assign_new(:form, fn ->
       to_form(Learning.change_lesson(lesson))
     end)}
  end

  @impl true
  def handle_event("validate", %{"lesson" => lesson_params}, socket) do # Expects course_module_id
    changeset = Learning.change_lesson(socket.assigns.lesson, lesson_params)
    {:noreply, assign(socket, form: to_form(changeset, action: :validate))}
  end

  def handle_event("save", %{"lesson" => lesson_params}, socket) do # Expects course_module_id
    save_lesson(socket, socket.assigns.action, lesson_params)
  end

  defp save_lesson(socket, :edit, lesson_params) do
    case Learning.update_lesson(socket.assigns.lesson, lesson_params) do
      {:ok, lesson} ->
        notify_parent({:saved, lesson})

        {:noreply,
         socket
         |> put_flash(:info, "Lesson updated successfully")
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp save_lesson(socket, :new, lesson_params) do
    case Learning.create_lesson(lesson_params) do
      {:ok, lesson} ->
        notify_parent({:saved, lesson})

        {:noreply,
         socket
         |> put_flash(:info, "Lesson created successfully")
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp notify_parent(msg), do: send(self(), {__MODULE__, msg})
end
