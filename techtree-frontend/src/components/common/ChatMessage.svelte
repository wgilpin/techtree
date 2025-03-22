<script>
  export let message;

  // Determine if the message is from the user or the assistant
  $: isUser = message.role === 'user';
</script>

<div class="message {isUser ? 'user' : 'assistant'}">
  <div class="avatar">
    {#if isUser}
      <div class="user-avatar">U</div>
    {:else}
      <div class="assistant-avatar">AI</div>
    {/if}
  </div>
  <div class="content">
    {#if isUser}
      <div class="name">You</div>
    {:else}
      <div class="name">Assistant</div>
    {/if}
    <div class="text">
      <!-- Check if content has markdown code and render accordingly -->
      {#if message.content.includes('```')}
        {#each message.content.split('```') as part, i}
          {#if i % 2 === 0}
            <p>{part}</p>
          {:else}
            <pre><code>{part}</code></pre>
          {/if}
        {/each}
      {:else}
        <p>{message.content}</p>
      {/if}
    </div>
  </div>
</div>

<style>
  .message {
    display: flex;
    margin-bottom: 1rem;
    padding: 0.5rem;
    border-radius: 8px;
  }

  .user {
    background-color: #f5f5f5;
  }

  .assistant {
    background-color: #e6f7ff;
  }

  .avatar {
    margin-right: 0.75rem;
    min-width: 32px;
  }

  .user-avatar, .assistant-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    color: white;
  }

  .user-avatar {
    background-color: #4caf50;
  }

  .assistant-avatar {
    background-color: #2196f3;
  }

  .content {
    flex: 1;
  }

  .name {
    font-weight: bold;
    margin-bottom: 0.25rem;
  }

  .text p {
    margin: 0 0 0.5rem 0;
    white-space: pre-wrap;
  }

  .text p:last-child {
    margin-bottom: 0;
  }

  pre {
    background-color: #f1f1f1;
    padding: 0.75rem;
    border-radius: 4px;
    overflow-x: auto;
  }

  code {
    font-family: monospace;
    white-space: pre;
  }
</style>