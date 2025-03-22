<script>
  export let message = "Loading...";
  export let size = "medium"; // small, medium, large
</script>

<div class="loading-container {size}">
  <div class="spinner"></div>
  {#if message}
    <div class="message">{message}</div>
  {/if}
</div>

<style>
  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }

  .small {
    min-height: 60px;
  }

  .medium {
    min-height: 100px;
  }

  .large {
    min-height: 200px;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-radius: 50%;
    border-top-color: #4CAF50;
    animation: spin 1s ease-in-out infinite;
  }

  .small .spinner {
    width: 24px;
    height: 24px;
    border-width: 3px;
  }

  .large .spinner {
    width: 64px;
    height: 64px;
    border-width: 6px;
  }

  .message {
    margin-top: 1rem;
    color: #666;
    font-size: 1rem;
  }

  .small .message {
    font-size: 0.8rem;
    margin-top: 0.5rem;
  }

  .large .message {
    font-size: 1.2rem;
    margin-top: 1.5rem;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>