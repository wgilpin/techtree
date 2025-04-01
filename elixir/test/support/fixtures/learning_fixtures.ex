defmodule TechTree.LearningFixtures do
  @moduledoc """
  This module defines test helpers for creating
  entities via the `TechTree.Learning` context.
  """

  @doc """
  Generate a syllabus.
  """
  def syllabus_fixture(attrs \\ %{}) do
    {:ok, syllabus} =
      attrs
      |> Enum.into(%{
        duration: "some duration",
        learning_objectives: %{},
        level: "some level",
        topic: "some topic"
      })
      |> TechTree.Learning.create_syllabus()

    syllabus
  end

  @doc """
  Generate a course_module.
  """
  def course_module_fixture(attrs \\ %{}) do
    {:ok, course_module} =
      attrs
      |> Enum.into(%{
        title: "some title",
        # syllabus_id needs to be provided or generated
        syllabus_id: attrs[:syllabus_id] || syllabus_fixture().id
      })
      |> TechTree.Learning.create_module()

    course_module
  end

  @doc """
  Generate a lesson.
  """
  def lesson_fixture(attrs \\ %{}) do
    {:ok, lesson} =
      attrs
      |> Enum.into(%{
        title: "some title",
        # course_module_id needs to be provided or generated
        course_module_id: attrs[:course_module_id] || course_module_fixture().id
      })
      |> TechTree.Learning.create_lesson()

    lesson
  end
end
