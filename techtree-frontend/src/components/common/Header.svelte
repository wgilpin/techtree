<script>
  import { createEventDispatcher } from "svelte";
  import { user } from "../../stores/user";
  import { auth } from "../../services/api";
  import { navigate } from "svelte-routing";

  const dispatch = createEventDispatcher();

  async function handleLogout() {
    try {
      await auth.logout();
      navigate("/login");
    } catch (error) {
      console.error("Logout error:", error);
    }
  }

  function toggleSidebar() {
    dispatch("toggleSidebar");
  }
</script>

<header>
  <div class="container">
    <div class="logo">
      <button class="menu-button" on:click={toggleSidebar}>
        <span class="menu-icon">☰</span>
      </button>
      <a href="/" class="brand">TechTree</a>
    </div>

    <nav>
      <ul>
        <li><a href="/">Dashboard</a></li>
        {#if $user.isAuthenticated}
          <li>
            <button class="user-menu">
              {$user.name || $user.email}
              <div class="dropdown">
                <a href="/profile">Profile</a>
                <button on:click={handleLogout}>Logout</button>
              </div>
            </button>
          </li>
        {:else}
          <li><a href="/login">Login</a></li>
          <li><a href="/register" class="register-btn">Register</a></li>
        {/if}
      </ul>
    </nav>
  </div>
</header>

<style>
  header {
    background-color: #333;
    color: white;
    padding: 1rem 0;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
  }

  .logo {
    display: flex;
    align-items: center;
  }

  .brand {
    font-size: 1.5rem;
    font-weight: bold;
    color: white;
    text-decoration: none;
    margin-left: 0.5rem;
  }

  .menu-button {
    background: none;
    border: none;
    color: white;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    margin-right: 0.5rem;
  }

  nav ul {
    display: flex;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  nav li {
    margin-left: 1.5rem;
  }

  nav a {
    color: white;
    text-decoration: none;
    transition: color 0.3s;
  }

  nav a:hover {
    color: #4CAF50;
  }

  .register-btn {
    background-color: #4CAF50;
    padding: 0.5rem 1rem;
    border-radius: 4px;
  }

  .register-btn:hover {
    background-color: #45a049;
  }

  .user-menu {
    background: none;
    border: none;
    color: white;
    cursor: pointer;
    position: relative;
  }

  .dropdown {
    display: none;
    position: absolute;
    right: 0;
    background-color: #fff;
    min-width: 160px;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
    z-index: 1;
    border-radius: 4px;
    margin-top: 0.5rem;
  }

  .dropdown a, .dropdown button {
    color: #333;
    padding: 12px 16px;
    text-decoration: none;
    display: block;
    text-align: left;
    width: 100%;
    background: none;
    border: none;
    cursor: pointer;
  }

  .dropdown a:hover, .dropdown button:hover {
    background-color: #f1f1f1;
  }

  .user-menu:hover .dropdown, .user-menu:focus .dropdown {
    display: block;
  }
</style>