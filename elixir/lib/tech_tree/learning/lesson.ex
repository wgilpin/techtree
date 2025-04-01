defmodule TechTree.Learning.Lesson do
  use Ecto.Schema
  import Ecto.Changeset

  alias TechTree.Learning.CourseModule

  @type t :: %__MODULE__{
          id: integer() | nil,
          title: String.t() | nil,
          course_module_id: integer() | nil, # Renamed foreign key
          module: CourseModule.t() | Ecto.Association.NotLoaded.t(),
          inserted_at: NaiveDateTime.t() | nil,
          updated_at: NaiveDateTime.t() | nil
        }
  @type changeset :: Ecto.Changeset.t()

  schema "lessons" do
    field :title, :string
    belongs_to :module, CourseModule, foreign_key: :course_module_id # Explicitly define FK field name

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(lesson, attrs) do
    lesson
    |> cast(attrs, [:title, :course_module_id]) # Renamed foreign key
    |> validate_required([:title, :course_module_id]) # Renamed foreign key
    |> foreign_key_constraint(:course_module_id) # Renamed foreign key
  end
end
