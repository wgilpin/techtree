defmodule TechTree.Repo.Migrations.CreateModules do
  use Ecto.Migration

  def change do
    create table(:course_modules) do
      add :title, :string
      add :syllabus_id, references(:syllabi, on_delete: :nothing)

      timestamps(type: :utc_datetime)
    end

    create index(:course_modules, [:syllabus_id])
  end
end
