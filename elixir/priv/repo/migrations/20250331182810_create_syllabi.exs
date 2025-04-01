defmodule TechTree.Repo.Migrations.CreateSyllabi do
  use Ecto.Migration

  def change do
    create table(:syllabi) do
      add :topic, :string
      add :level, :string
      add :duration, :string
      add :learning_objectives, :map

      timestamps(type: :utc_datetime)
    end
  end
end
