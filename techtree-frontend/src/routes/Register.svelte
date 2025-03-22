<script>
  import { onMount } from "svelte";
  import { navigate } from "svelte-routing";
  import { auth } from "../services/api";
  import { user, loadUserFromStorage } from "../stores/user";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";

  let name = "";
  let email = "";
  let password = "";
  let confirmPassword = "";
  let isLoading = false;
  let error = null;
  let agreeToTerms = false;

  onMount(() => {
    // Check if user is already logged in
    if (loadUserFromStorage()) {
      navigate("/");
    }
  });

  function validateForm() {
    if (!name || !email || !password || !confirmPassword) {
      error = "Please fill in all fields";
      return false;
    }

    if (password !== confirmPassword) {
      error = "Passwords do not match";
      return false;
    }

    if (password.length < 8) {
      error = "Password must be at least 8 characters long";
      return false;
    }

    if (!agreeToTerms) {
      error = "You must agree to the Terms of Service and Privacy Policy";
      return false;
    }

    return true;
  }

  async function handleRegister() {
    if (!validateForm()) {
      return;
    }

    try {
      isLoading = true;
      error = null;

      console.log("Attempting registration with:", { email, name });

      try {
        // Add a small delay to ensure the backend is ready
        await new Promise(resolve => setTimeout(resolve, 100));

        const result = await auth.register(email, password, name);
        console.log("Registration successful:", result);

        // Navigate to dashboard on successful registration
        navigate("/");
      } catch (err) {
        console.error("Registration error details:", {
          status: err.response?.status,
          statusText: err.response?.statusText,
          data: err.response?.data,
          headers: err.response?.headers,
          message: err.message
        });

        // Check for network errors
        if (!err.response) {
          error = "Network error. Please check your connection and try again.";
          console.error("Network error:", err);
        } else {
          throw err;
        }
      }
    } catch (err) {
      console.error("Registration error:", err);
      error = err.response?.data?.detail || "Registration failed. Please try again.";
    } finally {
      isLoading = false;
    }
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter') {
      handleRegister();
    }
  }
</script>

<div class="auth-container">
  <div class="auth-card">
    <div class="auth-header">
      <img src="/images/logo.jpeg" alt="TechTree Logo" class="auth-logo" />
      <h1>Create an Account</h1>
      <p>Join TechTree to start your personalized learning journey</p>
    </div>

    {#if error}
      <div class="error-message">
        {error}
      </div>
    {/if}

    <div class="auth-form">
      <div class="form-group">
        <label for="name">Full Name</label>
        <input
          type="text"
          id="name"
          bind:value={name}
          placeholder="Enter your full name"
          on:keypress={handleKeyPress}
          disabled={isLoading}
        />
      </div>

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
          placeholder="Create a password"
          on:keypress={handleKeyPress}
          disabled={isLoading}
        />
        <small class="form-hint">Password must be at least 8 characters long</small>
      </div>

      <div class="form-group">
        <label for="confirmPassword">Confirm Password</label>
        <input
          type="password"
          id="confirmPassword"
          bind:value={confirmPassword}
          placeholder="Confirm your password"
          on:keypress={handleKeyPress}
          disabled={isLoading}
        />
      </div>

      <div class="form-options">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={agreeToTerms} disabled={isLoading} />
          <span>I agree to the <a href="/terms">Terms of Service</a> and <a href="/privacy">Privacy Policy</a></span>
        </label>
      </div>

      <button
        class="auth-button"
        on:click={handleRegister}
        disabled={isLoading}
      >
        {#if isLoading}
          <LoadingIndicator size="small" message="" />
        {:else}
          Create Account
        {/if}
      </button>

      <div class="auth-footer">
        <p>Already have an account? <a href="/login">Login</a></p>
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

  input[type="text"],
  input[type="email"],
  input[type="password"] {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
    transition: border-color 0.3s;
  }

  input[type="text"]:focus,
  input[type="email"]:focus,
  input[type="password"]:focus {
    border-color: #4CAF50;
    outline: none;
  }

  .form-hint {
    display: block;
    margin-top: 0.25rem;
    font-size: 0.8rem;
    color: #666;
  }

  .form-options {
    display: flex;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
  }

  .checkbox-label {
    display: flex;
    align-items: flex-start;
    cursor: pointer;
  }

  .checkbox-label input {
    margin-right: 0.5rem;
    margin-top: 0.25rem;
  }

  .checkbox-label span {
    flex: 1;
  }

  .checkbox-label a {
    color: #2196f3;
    text-decoration: none;
  }

  .checkbox-label a:hover {
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
  }
</style>