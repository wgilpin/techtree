defmodule TechTree.Learning do
  @moduledoc """
  The Learning context.
  """

  import Ecto.Query, warn: false
  alias TechTree.Repo

  alias TechTree.Learning.Syllabus
  alias TechTree.Learning.CourseModule
  alias TechTree.Learning.Lesson

  @doc """
  Returns the list of syllabi.

  ## Examples

      iex> list_syllabi()
      [%Syllabus{}, ...]

  """
  @spec list_syllabi() :: list(Syllabus.t())
  def list_syllabi do
    Repo.all(Syllabus)
  end

  @doc """
  Gets a single syllabus.

  Raises `Ecto.NoResultsError` if the Syllabus does not exist.

  ## Examples

      iex> get_syllabus!(123)
      %Syllabus{}

      iex> get_syllabus!(456)
      ** (Ecto.NoResultsError)

  """
  @spec get_syllabus!(Syllabus.t() | Ecto.UUID.t() | integer()) :: Syllabus.t()
  def get_syllabus!(id), do: Repo.get!(Syllabus, id)

  @doc """
  Creates a syllabus.

  ## Examples

      iex> create_syllabus(%{field: value})
      {:ok, %Syllabus{}}

      iex> create_syllabus(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec create_syllabus(map()) :: {:ok, Syllabus.t()} | {:error, Syllabus.changeset()}
  def create_syllabus(attrs \\ %{}) do
    %Syllabus{}
    |> Syllabus.changeset(attrs)
    |> Repo.insert()
  end

  @doc """
  Updates a syllabus.

  ## Examples

      iex> update_syllabus(syllabus, %{field: new_value})
      {:ok, %Syllabus{}}

      iex> update_syllabus(syllabus, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec update_syllabus(Syllabus.t(), map()) :: {:ok, Syllabus.t()} | {:error, Syllabus.changeset()}
  def update_syllabus(%Syllabus{} = syllabus, attrs) do
    syllabus
    |> Syllabus.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a syllabus.

  ## Examples

      iex> delete_syllabus(syllabus)
      {:ok, %Syllabus{}}

      iex> delete_syllabus(syllabus)
      {:error, %Ecto.Changeset{}}

  """
  @spec delete_syllabus(Syllabus.t()) :: {:ok, Syllabus.t()} | {:error, Syllabus.changeset()}
  def delete_syllabus(%Syllabus{} = syllabus) do
    Repo.delete(syllabus)
  end

  @doc """
  Returns the list of modules.

  ## Examples

      iex> list_modules()
      [%Module{}, ...]

  """
  @spec list_modules() :: list(CourseModule.t())
  def list_modules do
    Repo.all(CourseModule)
  end

  @doc """
  Gets a single module.

  Raises `Ecto.NoResultsError` if the Module does not exist.

  ## Examples

      iex> get_module!(123)
      %Module{}

      iex> get_module!(456)
      ** (Ecto.NoResultsError)

  """
  @spec get_module!(CourseModule.t() | Ecto.UUID.t() | integer()) :: CourseModule.t()
  def get_module!(id), do: Repo.get!(CourseModule, id)

  @doc """
  Creates a module.

  ## Examples

      iex> create_module(%{field: value})
      {:ok, %Module{}}

      iex> create_module(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec create_module(map()) :: {:ok, CourseModule.t()} | {:error, CourseModule.changeset()}
  def create_module(attrs \\ %{}) do
    %CourseModule{}
    |> CourseModule.changeset(attrs)
    |> Repo.insert()
  end

  @doc """
  Updates a module.

  ## Examples

      iex> update_module(module, %{field: new_value})
      {:ok, %Module{}}

      iex> update_module(module, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec update_module(CourseModule.t(), map()) :: {:ok, CourseModule.t()} | {:error, CourseModule.changeset()}
  def update_module(%CourseModule{} = course_module, attrs) do
    course_module
    |> CourseModule.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a module.

  ## Examples

      iex> delete_module(module)
      {:ok, %Module{}}

      iex> delete_module(module)
      {:error, %Ecto.Changeset{}}

  """
  @spec delete_module(CourseModule.t()) :: {:ok, CourseModule.t()} | {:error, CourseModule.changeset()}
  def delete_module(%CourseModule{} = course_module) do
    Repo.delete(course_module)
  end

  @doc """
  Returns the list of lessons.

  ## Examples

      iex> list_lessons()
      [%Lesson{}, ...]

  """
  @spec list_lessons() :: list(Lesson.t())
  def list_lessons do
    Repo.all(Lesson)
  end

  @doc """
  Gets a single lesson.

  Raises `Ecto.NoResultsError` if the Lesson does not exist.

  ## Examples

      iex> get_lesson!(123)
      %Lesson{}

      iex> get_lesson!(456)
      ** (Ecto.NoResultsError)

  """
  @spec get_lesson!(Lesson.t() | Ecto.UUID.t() | integer()) :: Lesson.t()
  def get_lesson!(id), do: Repo.get!(Lesson, id)

  @doc """
  Creates a lesson.

  ## Examples

      iex> create_lesson(%{field: value})
      {:ok, %Lesson{}}

      iex> create_lesson(%{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec create_lesson(map()) :: {:ok, Lesson.t()} | {:error, Lesson.changeset()} # Note: Lesson.changeset now expects :course_module_id
  def create_lesson(attrs \\ %{}) do
    %Lesson{}
    |> Lesson.changeset(attrs)
    |> Repo.insert()
  end

  @doc """
  Updates a lesson.

  ## Examples

      iex> update_lesson(lesson, %{field: new_value})
      {:ok, %Lesson{}}

      iex> update_lesson(lesson, %{field: bad_value})
      {:error, %Ecto.Changeset{}}

  """
  @spec update_lesson(Lesson.t(), map()) :: {:ok, Lesson.t()} | {:error, Lesson.changeset()} # Note: Lesson.changeset now expects :course_module_id
  def update_lesson(%Lesson{} = lesson, attrs) do
    lesson
    |> Lesson.changeset(attrs)
    |> Repo.update()
  end

  @doc """
  Deletes a lesson.

  ## Examples

      iex> delete_lesson(lesson)
      {:ok, %Lesson{}}

      iex> delete_lesson(lesson)
      {:error, %Ecto.Changeset{}}

  """
  @spec delete_lesson(Lesson.t()) :: {:ok, Lesson.t()} | {:error, Lesson.changeset()}
  def delete_lesson(%Lesson{} = lesson) do
    Repo.delete(lesson)
  end


  @doc """
  Returns an `%Ecto.Changeset{}` for tracking syllabus changes.

  ## Examples

      iex> change_syllabus(syllabus)
      %Ecto.Changeset{data: %Syllabus{}}

  """
  @spec change_syllabus(Syllabus.t(), map()) :: Syllabus.changeset()
  def change_syllabus(%Syllabus{} = syllabus, attrs \\ %{}) do
    Syllabus.changeset(syllabus, attrs)
  end


  @doc """
  Returns an `%Ecto.Changeset{}` for tracking module changes.

  ## Examples

      iex> change_module(module)
      %Ecto.Changeset{data: %Module{}}

  """
  @spec change_module(CourseModule.t(), map()) :: CourseModule.changeset()
  def change_module(%CourseModule{} = course_module, attrs \\ %{}) do
    CourseModule.changeset(course_module, attrs)
  end


  @doc """
  Returns an `%Ecto.Changeset{}` for tracking lesson changes.

  ## Examples

      iex> change_lesson(lesson)
      %Ecto.Changeset{data: %Lesson{}}

  """
  @spec change_lesson(Lesson.t(), map()) :: Lesson.changeset()
  def change_lesson(%Lesson{} = lesson, attrs \\ %{}) do
    Lesson.changeset(lesson, attrs)
  end
end
