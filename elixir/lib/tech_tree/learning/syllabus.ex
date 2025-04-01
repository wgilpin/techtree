defmodule TechTree.Learning.Syllabus do
  use Ecto.Schema
  import Ecto.Changeset

  alias TechTree.Learning.CourseModule

  @type t :: %__MODULE__{
          id: integer() | nil,
          topic: String.t() | nil,
          level: String.t() | nil,
          duration: String.t() | nil,
          learning_objectives: map() | nil,
          modules: list(CourseModule.t()) | Ecto.Association.NotLoaded.t(),
          inserted_at: NaiveDateTime.t() | nil,
          updated_at: NaiveDateTime.t() | nil
        }
  @type changeset :: Ecto.Changeset.t()

  schema "syllabi" do
    field :level, :string
    field :topic, :string
    field :duration, :string
    field :learning_objectives, :map, default: %{}

    has_many :modules, CourseModule

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(syllabus, attrs) do
    syllabus
    |> cast(attrs, [:topic, :level, :duration, :learning_objectives])
    |> validate_required([:topic, :level, :duration]) # learning_objectives is optional
  end
end
