defmodule TechTreeWeb.SyllabusLive.FormComponent do
  use TechTreeWeb, :live_component

  alias TechTree.Learning

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <.header>
        {@title}
        <:subtitle>Use this form to manage syllabus records in your database.</:subtitle>
      </.header>

      <.simple_form
        for={@form}
        id="syllabus-form"
        phx-target={@myself}
        phx-change="validate"
        phx-submit="save"
      >
        <.input field={@form[:topic]} type="text" label="Topic" />
        <.input field={@form[:level]} type="text" label="Level" />
        <.input field={@form[:duration]} type="text" label="Duration" />
        <:actions>
          <.button phx-disable-with="Saving...">Save Syllabus</.button>
        </:actions>
      </.simple_form>
    </div>
    """
  end

  @impl true
  def update(%{syllabus: syllabus} = assigns, socket) do
    {:ok,
     socket
     |> assign(assigns)
     |> assign_new(:form, fn ->
       to_form(Learning.change_syllabus(syllabus))
     end)}
  end

  @impl true
  def handle_event("validate", %{"syllabus" => syllabus_params}, socket) do
    changeset = Learning.change_syllabus(socket.assigns.syllabus, syllabus_params)
    {:noreply, assign(socket, form: to_form(changeset, action: :validate))}
  end

  def handle_event("save", %{"syllabus" => syllabus_params}, socket) do
    save_syllabus(socket, socket.assigns.action, syllabus_params)
  end

  defp save_syllabus(socket, :edit, syllabus_params) do
    case Learning.update_syllabus(socket.assigns.syllabus, syllabus_params) do
      {:ok, syllabus} ->
        notify_parent({:saved, syllabus})

        {:noreply,
         socket
         |> put_flash(:info, "Syllabus updated successfully")
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp save_syllabus(socket, :new, syllabus_params) do
    case Learning.create_syllabus(syllabus_params) do
      {:ok, syllabus} ->
        notify_parent({:saved, syllabus})

        {:noreply,
         socket
         |> put_flash(:info, "Syllabus created successfully")
         |> push_patch(to: socket.assigns.patch)}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  defp notify_parent(msg), do: send(self(), {__MODULE__, msg})
end
