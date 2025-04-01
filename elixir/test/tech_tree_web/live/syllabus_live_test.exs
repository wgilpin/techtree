defmodule TechTreeWeb.SyllabusLiveTest do
  use TechTreeWeb.ConnCase

  import Phoenix.LiveViewTest
  import TechTree.LearningFixtures

  @create_attrs %{level: "some level", topic: "some topic", duration: "some duration", learning_objectives: %{}}
  @update_attrs %{level: "some updated level", topic: "some updated topic", duration: "some updated duration", learning_objectives: %{}}
  @invalid_attrs %{level: nil, topic: nil, duration: nil, learning_objectives: nil}

  defp create_syllabus(_) do
    syllabus = syllabus_fixture()
    %{syllabus: syllabus}
  end

  describe "Index" do
    setup [:create_syllabus]

    test "lists all syllabi", %{conn: conn, syllabus: syllabus} do
      {:ok, _index_live, html} = live(conn, ~p"/syllabi")

      assert html =~ "Listing Syllabi"
      assert html =~ syllabus.level
    end

    test "saves new syllabus", %{conn: conn} do
      {:ok, index_live, _html} = live(conn, ~p"/syllabi")

      assert index_live |> element("a", "New Syllabus") |> render_click() =~
               "New Syllabus"

      assert_patch(index_live, ~p"/syllabi/new")

      assert index_live
             |> form("#syllabus-form", syllabus: @invalid_attrs)
             |> render_change() =~ "can&#39;t be blank"

      assert index_live
             |> form("#syllabus-form", syllabus: @create_attrs)
             |> render_submit()

      assert_patch(index_live, ~p"/syllabi")

      html = render(index_live)
      assert html =~ "Syllabus created successfully"
      assert html =~ "some level"
    end

    test "updates syllabus in listing", %{conn: conn, syllabus: syllabus} do
      {:ok, index_live, _html} = live(conn, ~p"/syllabi")

      assert index_live |> element("#syllabi-#{syllabus.id} a", "Edit") |> render_click() =~
               "Edit Syllabus"

      assert_patch(index_live, ~p"/syllabi/#{syllabus}/edit")

      assert index_live
             |> form("#syllabus-form", syllabus: @invalid_attrs)
             |> render_change() =~ "can&#39;t be blank"

      assert index_live
             |> form("#syllabus-form", syllabus: @update_attrs)
             |> render_submit()

      assert_patch(index_live, ~p"/syllabi")

      html = render(index_live)
      assert html =~ "Syllabus updated successfully"
      assert html =~ "some updated level"
    end

    test "deletes syllabus in listing", %{conn: conn, syllabus: syllabus} do
      {:ok, index_live, _html} = live(conn, ~p"/syllabi")

      assert index_live |> element("#syllabi-#{syllabus.id} a", "Delete") |> render_click()
      refute has_element?(index_live, "#syllabi-#{syllabus.id}")
    end
  end

  describe "Show" do
    setup [:create_syllabus]

    test "displays syllabus", %{conn: conn, syllabus: syllabus} do
      {:ok, _show_live, html} = live(conn, ~p"/syllabi/#{syllabus}")

      assert html =~ "Show Syllabus"
      assert html =~ syllabus.level
    end

    test "updates syllabus within modal", %{conn: conn, syllabus: syllabus} do
      {:ok, show_live, _html} = live(conn, ~p"/syllabi/#{syllabus}")

      assert show_live |> element("a", "Edit") |> render_click() =~
               "Edit Syllabus"

      assert_patch(show_live, ~p"/syllabi/#{syllabus}/show/edit")

      assert show_live
             |> form("#syllabus-form", syllabus: @invalid_attrs)
             |> render_change() =~ "can&#39;t be blank"

      assert show_live
             |> form("#syllabus-form", syllabus: @update_attrs)
             |> render_submit()

      assert_patch(show_live, ~p"/syllabi/#{syllabus}")

      html = render(show_live)
      assert html =~ "Syllabus updated successfully"
      assert html =~ "some updated level"
    end
  end
end
