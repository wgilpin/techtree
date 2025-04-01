defmodule TechTree.Repo do
  use Ecto.Repo,
    otp_app: :tech_tree,
    adapter: Ecto.Adapters.SQLite3
end
