<script>
  import { Router, Route } from "svelte-routing";
  import { onMount } from "svelte";
  import Header from "./components/common/Header.svelte";
  import Footer from "./components/common/Footer.svelte";
  import Sidebar from "./components/common/Sidebar.svelte";
  import Dashboard from "./routes/Dashboard.svelte";
  import Onboarding from "./routes/Onboarding.svelte";
  import Syllabus from "./routes/Syllabus.svelte";
  import Lesson from "./routes/Lesson.svelte";
  import Login from "./routes/Login.svelte";
  import Register from "./routes/Register.svelte";
  import { user, loadUserFromStorage } from "./stores/user";

  let sidebarOpen = false;

  onMount(() => {
    // Check if user is logged in
    loadUserFromStorage();
  });

  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }
</script>

<Router>
  <div class="app-container">
    <Header on:toggleSidebar={toggleSidebar} />

    <main class="content">
      <Sidebar open={sidebarOpen} />

      <div class="page-content">
        <Route path="/" component={Dashboard} />
        <Route path="/login" component={Login} />
        <Route path="/register" component={Register} />
        <Route path="/onboard/:topic?" let:params>
          <Onboarding topic={params.topic} />
        </Route>
        <Route path="/syllabus/:topic/:level" let:params>
          <Syllabus topic={params.topic} level={params.level} />
        </Route>
        <Route path="/lesson/:syllabusId/:module/:lesson" let:params>
          <Lesson
            syllabusId={params.syllabusId}
            module={params.module}
            lesson={params.lesson}
          />
        </Route>
      </div>
    </main>

    <Footer />
  </div>
</Router>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
    background-color: #f5f5f5;
    color: #333;
    line-height: 1.6;
  }

  :global(*, *::before, *::after) {
    box-sizing: border-box;
  }

  .app-container {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .content {
    display: flex;
    flex: 1;
    position: relative;
  }

  .page-content {
    flex: 1;
    padding: 20px;
    padding-top: 0;
    margin-top: 0;
  }

  @media (max-width: 768px) {
    .page-content {
      padding: 10px;
    }
  }
</style>