<script>
  import { user, sessionContext } from "../../stores/user";
  import { navigate } from "svelte-routing";

  export let open = false;

  function closeNav() {
    open = false;
  }
</script>

<div class="sidebar" class:open>
  <div class="sidebar-content">
    <div class="sidebar-header">
      <button class="close-btn" on:click={closeNav}>&times;</button>
    </div>

    <div class="nav-section">
      <h3>Learning</h3>
      <ul>
        <li>
          <a href="/" on:click={closeNav}>Dashboard</a>
        </li>
        <li>
          <a href="/onboard" on:click={closeNav}>Start New Topic</a>
        </li>
        {#if $sessionContext.currentTopic && $sessionContext.currentLevel}
          <li>
            <a
              href={`/syllabus/${$sessionContext.currentTopic}/${$sessionContext.currentLevel}`}
              on:click={closeNav}
            >
              Current Syllabus
            </a>
          </li>
        {/if}
        {#if $sessionContext.currentSyllabusId && $sessionContext.currentModuleTitle}
          <li>
            <a
              href={`/lesson/${$sessionContext.currentSyllabusId}/0/0`}
              on:click={closeNav}
            >
              Current Lesson
            </a>
          </li>
        {/if}
      </ul>
    </div>

    {#if $user.isAuthenticated}
      <div class="nav-section">
        <h3>My Account</h3>
        <ul>
          <li>
            <a href="/profile" on:click={closeNav}>Profile</a>
          </li>
          <li>
            <a href="/progress" on:click={closeNav}>Progress Tracking</a>
          </li>
        </ul>
      </div>
    {/if}

    <div class="nav-section">
      <h3>Resources</h3>
      <ul>
        <li>
          <a href="/help" on:click={closeNav}>Help Center</a>
        </li>
        <li>
          <a href="/about" on:click={closeNav}>About TechTree</a>
        </li>
      </ul>
    </div>
  </div>

  <div class="sidebar-overlay" on:click={closeNav}></div>
</div>

<style>
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100%;
    width: 0;
    z-index: 200;
    overflow-x: hidden;
    transition: 0.3s;
  }

  .sidebar.open {
    width: 100%;
  }

  .sidebar-content {
    position: absolute;
    top: 0;
    left: 0;
    width: 250px;
    height: 100%;
    background-color: white;
    box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1);
    padding: 20px 0;
    overflow-y: auto;
    transform: translateX(-100%);
    transition: transform 0.3s ease-in-out;
  }

  .sidebar.open .sidebar-content {
    transform: translateX(0);
  }

  .sidebar-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.5);
    opacity: 0;
    visibility: hidden;
    transition: 0.3s;
  }

  .sidebar.open .sidebar-overlay {
    opacity: 1;
    visibility: visible;
  }

  .sidebar-header {
    display: flex;
    justify-content: flex-end;
    padding: 0 20px 20px;
    border-bottom: 1px solid #eee;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #333;
  }

  .nav-section {
    padding: 15px 0;
    border-bottom: 1px solid #eee;
  }

  .nav-section h3 {
    padding: 0 20px;
    margin: 0 0 10px;
    font-size: 0.8rem;
    text-transform: uppercase;
    color: #666;
  }

  .nav-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .nav-section li {
    padding: 0;
  }

  .nav-section a {
    display: block;
    padding: 10px 20px;
    color: #333;
    text-decoration: none;
    transition: background-color 0.3s;
  }

  .nav-section a:hover, .nav-section a:focus {
    background-color: #f5f5f5;
  }
</style>