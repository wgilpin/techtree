defmodule TechTreeWeb.Router do
  use TechTreeWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {TechTreeWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  scope "/", TechTreeWeb do
    pipe_through :browser

    get "/", PageController, :home


    # Syllabus LiveView Routes
    live "/syllabi", SyllabusLive.Index, :index
    live "/syllabi/new", SyllabusLive.Index, :new
    live "/syllabi/:id/edit", SyllabusLive.Index, :edit



    # Course Module LiveView Routes
    live "/course_modules", CourseModuleLive.Index, :index
    live "/course_modules/new", CourseModuleLive.Index, :new
    live "/course_modules/:id/edit", CourseModuleLive.Index, :edit


    # Lesson LiveView Routes
    live "/lessons", LessonLive.Index, :index
    live "/lessons/new", LessonLive.Index, :new
    live "/lessons/:id/edit", LessonLive.Index, :edit

    live "/lessons/:id", LessonLive.Show, :show
    live "/lessons/:id/show/edit", LessonLive.Show, :edit
    live "/course_modules/:id", CourseModuleLive.Show, :show
    live "/course_modules/:id/show/edit", CourseModuleLive.Show, :edit
    live "/syllabi/:id", SyllabusLive.Show, :show


    # Start Learning Flow
    live "/start_learning", StartLearningLive, :index
    live "/syllabi/:id/show/edit", SyllabusLive.Show, :edit
  end

  # Other scopes may use custom stacks.
  # scope "/api", TechTreeWeb do
  #   pipe_through :api
  # end

  # Enable LiveDashboard and Swoosh mailbox preview in development
  if Application.compile_env(:tech_tree, :dev_routes) do
    # If you want to use the LiveDashboard in production, you should put
    # it behind authentication and allow only admins to access it.
    # If your application does not have an admins-only section yet,
    # you can use Plug.BasicAuth to set up some basic authentication
    # as long as you are also using SSL (which you should anyway).
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through :browser

      live_dashboard "/dashboard", metrics: TechTreeWeb.Telemetry
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
