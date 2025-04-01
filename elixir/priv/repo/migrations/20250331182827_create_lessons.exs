defmodule TechTree.Repo.Migrations.CreateLessons do
  use Ecto.Migration

  def change do
    create table(:lessons) do
      add :title, :string
      add :course_module_id, references(:course_modules, on_delete: :nothing)

      timestamps(type: :utc_datetime)
    end

    create index(:lessons, [:course_module_id])
  end
end
