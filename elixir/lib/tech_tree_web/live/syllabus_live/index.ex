defmodule TechTreeWeb.SyllabusLive.Index do
  use TechTreeWeb, :live_view

  alias TechTree.Learning
  alias TechTree.Learning.Syllabus

  @impl true
  def mount(_params, _session, socket) do
    {:ok, stream(socket, :syllabi, Learning.list_syllabi())}
  end

  @impl true
  def handle_params(params, _url, socket) do
    {:noreply, apply_action(socket, socket.assigns.live_action, params)}
  end

  defp apply_action(socket, :edit, %{"id" => id}) do
    socket
    |> assign(:page_title, "Edit Syllabus")
    |> assign(:syllabus, Learning.get_syllabus!(id))
  end

  defp apply_action(socket, :new, _params) do
    socket
    |> assign(:page_title, "New Syllabus")
    |> assign(:syllabus, %Syllabus{})
  end

  defp apply_action(socket, :index, _params) do
    socket
    |> assign(:page_title, "Listing Syllabi")
    |> assign(:syllabus, nil)
  end

  @impl true
  def handle_info({TechTreeWeb.SyllabusLive.FormComponent, {:saved, syllabus}}, socket) do
    {:noreply, stream_insert(socket, :syllabi, syllabus)}
  end

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    syllabus = Learning.get_syllabus!(id)
    {:ok, _} = Learning.delete_syllabus(syllabus)

    {:noreply, stream_delete(socket, :syllabi, syllabus)}
  end
end
