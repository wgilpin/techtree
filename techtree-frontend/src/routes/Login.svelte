<script>
  import { onMount } from "svelte";
  import { navigate } from "svelte-routing";
  import { auth } from "../services/api";
  import { user, loadUserFromStorage } from "../stores/user";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";

  let email = "";
  let password = "";
  let isLoading = false;
  let error = null;
  let rememberMe = false;

  onMount(() => {
    // Check if user is already logged in
    if (loadUserFromStorage()) {
      navigate("/");
    }
  });

  async function handleLogin() {
    if (!email || !password) {
      error = "Please enter both email and password";
      return;
    }

    try {
      isLoading = true;
      error = null;

      const result = await auth.login(email, password);

      // Navigate to dashboard on successful login
      navigate("/");
    } catch (err) {
      console.error("Login error:", err);
      error = err.response?.data?.detail || "Invalid email or password. Please try again.";
    } finally {
      isLoading = false;
    }
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter') {
      handleLogin();
    }
  }
</script>

<div class="auth-container">
  <div class="auth-card">
    <div class="auth-header">
      <img src="/images/logo.jpeg" alt="TechTree Logo" class="auth-logo" />
      <h1>Login to TechTree</h1>
      <p>Welcome back! Please enter your credentials to continue.</p>
    </div>

    {#if error}
      <div class="error-message">
        {error}
      </div>
    {/if}

    <div class="auth-form">
      <div class="form-group">
        <label for="email">Email</label>
        <input
          type="email"
          id="email"
          bind:value={email}
          placeholder="Enter your email"
          on:keypress={handleKeyPress}
          disabled={isLoading}
        />
      </div>

      <div class="form-group">
        <label for="password">Password</label>
        <input
          type="password"
          id="password"
          bind:value={password}
          placeholder="Enter your password"
          on:keypress={handleKeyPress}
          disabled={isLoading}
        />
      </div>

      <div class="form-options">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={rememberMe} disabled={isLoading} />
          <span>Remember me</span>
        </label>
        <a href="/forgot-password" class="forgot-password">Forgot password?</a>
      </div>

      <button
        class="auth-button"
        on:click={handleLogin}
        disabled={isLoading}
      >
        {#if isLoading}
          <LoadingIndicator size="small" message="" />
        {:else}
          Login
        {/if}
      </button>

      <div class="auth-footer">
        <p>Don't have an account? <a href="/register">Register</a></p>
      </div>
    </div>
  </div>
</div>

<style>
  .auth-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: calc(100vh - 200px);
    padding: 2rem;
  }

  .auth-card {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    width: 100%;
    max-width: 450px;
    padding: 2rem;
  }

  .auth-header {
    text-align: center;
    margin-bottom: 2rem;
  }

  .auth-logo {
    max-width: 120px;
    margin-bottom: 1rem;
  }

  .auth-header h1 {
    margin-bottom: 0.5rem;
    color: #333;
  }

  .auth-header p {
    color: #666;
    margin: 0;
  }

  .error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .auth-form {
    display: flex;
    flex-direction: column;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #333;
  }

  input[type="email"],
  input[type="password"] {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
    transition: border-color 0.3s;
  }

  input[type="email"]:focus,
  input[type="password"]:focus {
    border-color: #4CAF50;
    outline: none;
  }

  .form-options {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    cursor: pointer;
  }

  .checkbox-label input {
    margin-right: 0.5rem;
  }

  .forgot-password {
    color: #2196f3;
    text-decoration: none;
  }

  .forgot-password:hover {
    text-decoration: underline;
  }

  .auth-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.75rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 48px;
  }

  .auth-button:hover:not(:disabled) {
    background-color: #45a049;
  }

  .auth-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  .auth-footer {
    text-align: center;
    margin-top: 1.5rem;
    font-size: 0.9rem;
    color: #666;
  }

  .auth-footer a {
    color: #2196f3;
    text-decoration: none;
  }

  .auth-footer a:hover {
    text-decoration: underline;
  }

  @media (max-width: 500px) {
    .auth-card {
      padding: 1.5rem;
    }

    .form-options {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }
  }
</style>