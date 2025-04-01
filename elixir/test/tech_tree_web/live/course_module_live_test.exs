defmodule TechTreeWeb.CourseModuleLiveTest do # Renamed
  use TechTreeWeb.ConnCase

  import Phoenix.LiveViewTest
  import TechTree.LearningFixtures

  @create_attrs %{title: "some title"}
  @update_attrs %{title: "some updated title"}
  @invalid_attrs %{title: nil}

  defp create_course_module(_) do # Renamed function
    # Need syllabus for foreign key
    syllabus = syllabus_fixture()
    course_module = course_module_fixture(%{syllabus_id: syllabus.id}) # Renamed fixture
    %{course_module: course_module} # Renamed key
  end

  describe "Index" do
    setup [:create_course_module] # Renamed setup function

    test "lists all course_modules", %{conn: conn, course_module: course_module} do # Renamed key
      {:ok, _index_live, html} = live(conn, ~p"/course_modules") # Renamed path

      assert html =~ "Listing Course Modules" # Renamed text
      assert html =~ course_module.title
    end

    test "saves new course_module", %{conn: conn} do
      {:ok, index_live, _html} = live(conn, ~p"/course_modules") # Renamed path

      assert index_live |> element("a", "New Course Module") |> render_click() # Renamed text
      assert index_live |> form("#course-module-form", course_module: @invalid_attrs) |> render_change() =~ # Renamed id & key
               "can&#39;t be blank"

      # Need syllabus_id for valid attrs now
      syllabus = syllabus_fixture()
      create_attrs = Map.put(@create_attrs, :syllabus_id, syllabus.id)

      assert index_live |> form("#course-module-form", course_module: create_attrs) |> render_submit() # Renamed id & key
      assert_patch(index_live, ~p"/course_modules") # Renamed path

      html = render(index_live)
      assert html =~ "Course Module created successfully" # Renamed text
      assert html =~ "some title"
    end

    test "updates course_module in listing", %{conn: conn, course_module: course_module} do # Renamed key
      {:ok, index_live, _html} = live(conn, ~p"/course_modules") # Renamed path

      assert index_live |> element("#course_modules-#{course_module.id} a", "Edit") |> render_click() # Renamed id
      assert index_live |> form("#course-module-form", course_module: @invalid_attrs) |> render_change() =~ # Renamed id & key
               "can&#39;t be blank"

      assert index_live |> form("#course-module-form", course_module: @update_attrs) |> render_submit() # Renamed id & key
      assert_patch(index_live, ~p"/course_modules") # Renamed path

      html = render(index_live)
      assert html =~ "Course Module updated successfully" # Renamed text
      assert html =~ "some updated title"
    end

    test "deletes course_module in listing", %{conn: conn, course_module: course_module} do # Renamed key
      {:ok, index_live, _html} = live(conn, ~p"/course_modules") # Renamed path
      assert index_live |> element("#course_modules-#{course_module.id} a", "Delete") |> render_click() # Renamed id
      refute has_element?(index_live, "#course_modules-#{course_module.id}") # Renamed id
    end
  end

  describe "Show" do
    setup [:create_course_module] # Renamed setup function

    test "displays course_module", %{conn: conn, course_module: course_module} do # Renamed key
      {:ok, _show_live, html} = live(conn, ~p"/course_modules/#{course_module}") # Renamed path

      assert html =~ "Show Course Module" # Renamed text
      assert html =~ course_module.title
    end

    test "updates course_module within modal", %{conn: conn, course_module: course_module} do # Renamed key
      {:ok, show_live, _html} = live(conn, ~p"/course_modules/#{course_module}") # Renamed path

      assert show_live |> element("a", "Edit") |> render_click()
      assert show_live |> form("#course-module-form", course_module: @invalid_attrs) |> render_change() =~ # Renamed id & key
               "can&#39;t be blank"

      assert show_live |> form("#course-module-form", course_module: @update_attrs) |> render_submit() # Renamed id & key
      assert_patch(show_live, ~p"/course_modules/#{course_module}") # Renamed path

      html = render(show_live)
      assert html =~ "Course Module updated successfully" # Renamed text
      assert html =~ "some updated title"
    end
  end
end
