defmodule TechTreeWeb.CourseModuleLive.Show do # Renamed
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
     |> assign(:current_module, Learning.get_module!(id))} # Kept assign name
  end

  defp page_title(:show), do: "Show Course Module" # Renamed
  defp page_title(:edit), do: "Edit Course Module" # Renamed
end
