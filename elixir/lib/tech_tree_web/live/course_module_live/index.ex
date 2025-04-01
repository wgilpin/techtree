defmodule TechTreeWeb.CourseModuleLive.Index do
  use TechTreeWeb, :live_view

  alias TechTree.Learning
  alias TechTree.Learning.CourseModule # Renamed

  @impl true
  def mount(_params, _session, socket) do
    {:ok, stream(socket, :course_modules, Learning.list_modules())} # Renamed stream
  end

  @impl true
  def handle_params(params, _url, socket) do
    {:noreply, apply_action(socket, socket.assigns.live_action, params)}
  end

  defp apply_action(socket, :edit, %{"id" => id}) do
    socket
    |> assign(:page_title, "Edit Course Module") # Renamed
    |> assign(:current_module, Learning.get_module!(id)) # Kept assign name
  end

  defp apply_action(socket, :new, _params) do
    socket
    |> assign(:page_title, "New Course Module") # Renamed
    |> assign(:current_module, %CourseModule{}) # Renamed struct, kept assign name
  end

  defp apply_action(socket, :index, _params) do
    socket
    |> assign(:page_title, "Listing Course Modules") # Renamed
    |> assign(:current_module, nil) # Kept assign name
  end

  @impl true
  # Renamed FormComponent module name
  def handle_info({TechTreeWeb.CourseModuleLive.FormComponent, {:saved, course_module}}, socket) do
    {:noreply, stream_insert(socket, :course_modules, course_module)} # Renamed stream
  end

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    course_module = Learning.get_module!(id) # Renamed variable
    {:ok, _} = Learning.delete_module(course_module) # Renamed variable

    {:noreply, stream_delete(socket, :course_modules, course_module)} # Renamed stream & variable
  end
end
