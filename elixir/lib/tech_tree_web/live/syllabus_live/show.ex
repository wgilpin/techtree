defmodule TechTreeWeb.SyllabusLive.Show do
  use TechTreeWeb, :live_view

  alias TechTree.Learning

  @impl true
  def mount(_params, _session, socket) do
    {:ok, socket}
  end

  @impl true
  def handle_params(%{"id" => id}, _, socket) do
    {:noreply,
     socket
     |> assign(:page_title, page_title(socket.assigns.live_action))
     |> assign(:syllabus, Learning.get_syllabus!(id))}
  end

  defp page_title(:show), do: "Show Syllabus"
  defp page_title(:edit), do: "Edit Syllabus"
end
