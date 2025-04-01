defmodule TechTree.Learning.CourseModule do
  use Ecto.Schema
  import Ecto.Changeset

  alias TechTree.Learning.{Syllabus, Lesson}

  @type t :: %__MODULE__{
          id: integer() | nil,
          title: String.t() | nil,
          syllabus_id: integer() | nil,
          syllabus: Syllabus.t() | Ecto.Association.NotLoaded.t(),
          lessons: list(Lesson.t()) | Ecto.Association.NotLoaded.t(),
          inserted_at: NaiveDateTime.t() | nil,
          updated_at: NaiveDateTime.t() | nil
        }
  @type changeset :: Ecto.Changeset.t()

  schema "modules" do # Table name will be updated in migration later
    field :title, :string
    belongs_to :syllabus, Syllabus
    has_many :lessons, Lesson, foreign_key: :course_module_id

    timestamps(type: :utc_datetime)
  end

  @doc false
  def changeset(course_module, attrs) do
    course_module
    |> cast(attrs, [:title, :syllabus_id])
    |> validate_required([:title, :syllabus_id])
    |> foreign_key_constraint(:syllabus_id)
  end
end
