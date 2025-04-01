defmodule TechTree.LearningTest do
  use TechTree.DataCase

  alias TechTree.Learning

  describe "syllabi" do
    alias TechTree.Learning.Syllabus

    import TechTree.LearningFixtures

    @invalid_attrs %{level: nil, topic: nil, duration: nil, learning_objectives: nil}

    test "list_syllabi/0 returns all syllabi" do
      syllabus = syllabus_fixture()
      assert Learning.list_syllabi() == [syllabus]
    end

    test "get_syllabus!/1 returns the syllabus with given id" do
      syllabus = syllabus_fixture()
      assert Learning.get_syllabus!(syllabus.id) == syllabus
    end

    test "create_syllabus/1 with valid data creates a syllabus" do
      valid_attrs = %{level: "some level", topic: "some topic", duration: "some duration", learning_objectives: %{}}

      assert {:ok, %Syllabus{} = syllabus} = Learning.create_syllabus(valid_attrs)
      assert syllabus.level == "some level"
      assert syllabus.topic == "some topic"
      assert syllabus.duration == "some duration"
      assert syllabus.learning_objectives == %{}
    end

    test "create_syllabus/1 with invalid data returns error changeset" do
      assert {:error, %Ecto.Changeset{}} = Learning.create_syllabus(@invalid_attrs)
    end

    test "update_syllabus/2 with valid data updates the syllabus" do
      syllabus = syllabus_fixture()
      update_attrs = %{level: "some updated level", topic: "some updated topic", duration: "some updated duration", learning_objectives: %{}}

      assert {:ok, %Syllabus{} = syllabus} = Learning.update_syllabus(syllabus, update_attrs)
      assert syllabus.level == "some updated level"
      assert syllabus.topic == "some updated topic"
      assert syllabus.duration == "some updated duration"
      assert syllabus.learning_objectives == %{}
    end

    test "update_syllabus/2 with invalid data returns error changeset" do
      syllabus = syllabus_fixture()
      assert {:error, %Ecto.Changeset{}} = Learning.update_syllabus(syllabus, @invalid_attrs)
      assert syllabus == Learning.get_syllabus!(syllabus.id)
    end

    test "delete_syllabus/1 deletes the syllabus" do
      syllabus = syllabus_fixture()
      assert {:ok, %Syllabus{}} = Learning.delete_syllabus(syllabus)
      assert_raise Ecto.NoResultsError, fn -> Learning.get_syllabus!(syllabus.id) end
    end

    test "change_syllabus/1 returns a syllabus changeset" do
      syllabus = syllabus_fixture()
      assert %Ecto.Changeset{} = Learning.change_syllabus(syllabus)
    end
  end

  describe "course_modules" do
    alias TechTree.Learning.CourseModule

    import TechTree.LearningFixtures

    @invalid_attrs %{title: nil}

    test "list_modules/0 returns all modules" do
      course_module = course_module_fixture()
      assert Learning.list_modules() == [course_module]
    end

    test "get_module!/1 returns the module with given id" do
      course_module = course_module_fixture()
      assert Learning.get_module!(course_module.id) == course_module
    end

    test "create_module/1 with valid data creates a module" do
      # Need syllabus_id for valid attrs now
      syllabus = syllabus_fixture()
      valid_attrs = %{title: "some title", syllabus_id: syllabus.id}

      assert {:ok, %CourseModule{} = course_module} = Learning.create_module(valid_attrs)
      assert course_module.title == "some title"
      assert course_module.syllabus_id == syllabus.id
    end

    test "create_module/1 with invalid data returns error changeset" do
      # Need to test invalid syllabus_id too
      assert {:error, %Ecto.Changeset{}} = Learning.create_module(@invalid_attrs)
      assert {:error, %Ecto.Changeset{errors: [syllabus_id: _]}} = Learning.create_module(%{title: "valid title", syllabus_id: -1})
    end

    test "update_module/2 with valid data updates the module" do
      course_module = course_module_fixture()
      update_attrs = %{title: "some updated title"}

      assert {:ok, %CourseModule{} = course_module} = Learning.update_module(course_module, update_attrs)
      assert course_module.title == "some updated title"
    end

    test "update_module/2 with invalid data returns error changeset" do
      course_module = course_module_fixture()
      assert {:error, %Ecto.Changeset{}} = Learning.update_module(course_module, @invalid_attrs)
      assert course_module == Learning.get_module!(course_module.id)
    end

    test "delete_module/1 deletes the module" do
      course_module = course_module_fixture()
      assert {:ok, %CourseModule{}} = Learning.delete_module(course_module)
      assert_raise Ecto.NoResultsError, fn -> Learning.get_module!(course_module.id) end
    end

    test "change_module/1 returns a module changeset" do
      course_module = course_module_fixture()
      assert %Ecto.Changeset{} = Learning.change_module(course_module)
    end
  end

  describe "lessons" do
    alias TechTree.Learning.Lesson

    import TechTree.LearningFixtures

    @invalid_attrs %{title: nil}

    test "list_lessons/0 returns all lessons" do
      lesson = lesson_fixture()
      assert Learning.list_lessons() == [lesson]
    end

    test "get_lesson!/1 returns the lesson with given id" do
      lesson = lesson_fixture()
      assert Learning.get_lesson!(lesson.id) == lesson
    end

    test "create_lesson/1 with valid data creates a lesson" do
      # Need course_module_id for valid attrs now
      course_module = course_module_fixture()
      valid_attrs = %{title: "some title", course_module_id: course_module.id}

      assert {:ok, %Lesson{} = lesson} = Learning.create_lesson(valid_attrs)
      assert lesson.title == "some title"
      assert lesson.course_module_id == course_module.id
    end

    test "create_lesson/1 with invalid data returns error changeset" do
      # Need to test invalid course_module_id too
      assert {:error, %Ecto.Changeset{}} = Learning.create_lesson(@invalid_attrs)
      assert {:error, %Ecto.Changeset{errors: [course_module_id: _]}} = Learning.create_lesson(%{title: "valid title", course_module_id: -1})
    end

    test "update_lesson/2 with valid data updates the lesson" do
      lesson = lesson_fixture()
      update_attrs = %{title: "some updated title"}

      assert {:ok, %Lesson{} = lesson} = Learning.update_lesson(lesson, update_attrs)
      assert lesson.title == "some updated title"
    end

    test "update_lesson/2 with invalid data returns error changeset" do
      lesson = lesson_fixture()
      assert {:error, %Ecto.Changeset{}} = Learning.update_lesson(lesson, @invalid_attrs)
      assert lesson == Learning.get_lesson!(lesson.id)
    end

    test "delete_lesson/1 deletes the lesson" do
      lesson = lesson_fixture()
      assert {:ok, %Lesson{}} = Learning.delete_lesson(lesson)
      assert_raise Ecto.NoResultsError, fn -> Learning.get_lesson!(lesson.id) end
    end

    test "change_lesson/1 returns a lesson changeset" do
      lesson = lesson_fixture()
      assert %Ecto.Changeset{} = Learning.change_lesson(lesson)
    end
  end
end
