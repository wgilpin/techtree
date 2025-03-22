<script>
  import { onMount } from "svelte";
  import { navigate } from "svelte-routing";
  import { onboarding } from "../services/api";
  import { sessionContext, messageHistory } from "../stores/user";
  import ChatMessage from "../components/common/ChatMessage.svelte";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";

  export let topic = null;

  let currentQuestion = "";
  let difficulty = "";
  let userAnswer = "";
  let isLoading = false;
  let assessmentComplete = false;
  let assessmentResult = null;
  let error = null;
  let topicInput = "";

  onMount(async () => {
    // Clear message history when starting fresh
    messageHistory.set([]);

    if (!topic) {
      return; // Wait for user to enter a topic
    }

    startAssessment(topic);
  });

  async function startAssessment(topicValue) {
    if (!topicValue.trim()) return;

    topic = topicValue.trim();
    isLoading = true;
    error = null;

    try {
      // Start assessment
      const result = await onboarding.startAssessment(topic);
      currentQuestion = result.question;
      difficulty = result.difficulty;

      // Add initial message
      messageHistory.update(msgs => [
        ...msgs,
        {
          role: "assistant",
          content: `Starting knowledge assessment for "${topic}"\n\n[${difficulty}] ${currentQuestion}`
        }
      ]);

      // Update session context
      sessionContext.update(ctx => ({
        ...ctx,
        currentTopic: topic
      }));
    } catch (err) {
      console.error("Error starting assessment:", err);
      error = "Failed to start the assessment. Please try again.";
    } finally {
      isLoading = false;
    }
  }

  async function handleSubmitAnswer() {
    if (!userAnswer.trim()) return;

    messageHistory.update(msgs => [
      ...msgs,
      { role: "user", content: userAnswer }
    ]);

    const answer = userAnswer;
    userAnswer = ""; // Clear input
    error = null;
    isLoading = true;

    try {
      const result = await onboarding.submitAnswer(answer);

      if (result.is_complete) {
        // Assessment complete
        assessmentComplete = true;
        assessmentResult = result;

        messageHistory.update(msgs => [
          ...msgs,
          {
            role: "assistant",
            content: result.feedback || "Your assessment is complete!"
          },
          {
            role: "assistant",
            content: `Based on your responses, your knowledge level for "${topic}" is: **${result.knowledge_level}**\n\nI'll now create a personalized syllabus based on your knowledge level.`
          }
        ]);

        // Update session context with assessment result
        sessionContext.update(ctx => ({
          ...ctx,
          currentLevel: result.knowledge_level
        }));

        // Navigate to syllabus after a brief delay
        setTimeout(() => {
          navigate(`/syllabus/${encodeURIComponent(topic)}/${encodeURIComponent(result.knowledge_level)}`);
        }, 3000);
      } else {
        // Continue with next question
        currentQuestion = result.question;
        difficulty = result.difficulty;

        messageHistory.update(msgs => [
          ...msgs,
          {
            role: "assistant",
            content: result.feedback || "Thanks for your answer."
          },
          {
            role: "assistant",
            content: `[${difficulty}] ${currentQuestion}`
          }
        ]);
      }
    } catch (err) {
      console.error("Error submitting answer:", err);
      error = "Failed to process your answer. Please try again.";
    } finally {
      isLoading = false;
    }
  }

  function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!topic) {
        startAssessment(topicInput);
      } else {
        handleSubmitAnswer();
      }
    }
  }
</script>

<div class="onboarding-container">
  <h1>Knowledge Assessment{topic ? `: ${topic}` : ""}</h1>

  <div class="chat-container">
    {#each $messageHistory as message}
      <ChatMessage {message} />
    {/each}

    {#if isLoading}
      <div class="loading-wrapper">
        <LoadingIndicator size="small" message="Thinking..." />
      </div>
    {/if}

    {#if error}
      <div class="error-message">
        {error}
      </div>
    {/if}
  </div>

  {#if !topic}
    <div class="topic-input">
      <h2>What topic would you like to learn about?</h2>
      <p class="description">
        Enter a topic you're interested in, and I'll assess your current knowledge
        to create a personalized learning path.
      </p>
      <div class="input-group">
        <input
          bind:value={topicInput}
          placeholder="Enter a topic (e.g., 'Python Programming', 'Machine Learning')"
          on:keypress={handleKeyPress}
        />
        <button class="primary-button" on:click={() => startAssessment(topicInput)}>
          Start Assessment
        </button>
      </div>
    </div>
  {:else if !assessmentComplete}
    <div class="answer-input">
      <textarea
        bind:value={userAnswer}
        placeholder="Type your answer here..."
        on:keypress={handleKeyPress}
        rows="3"
        disabled={isLoading}
      ></textarea>
      <button
        class="primary-button"
        on:click={handleSubmitAnswer}
        disabled={isLoading || !userAnswer.trim()}
      >
        Submit Answer
      </button>
    </div>
  {:else}
    <div class="assessment-result">
      <h2>Assessment Complete!</h2>
      <p>Knowledge level: <strong>{assessmentResult.knowledge_level}</strong></p>
      <p>Redirecting to your personalized syllabus...</p>
      <LoadingIndicator size="small" />
    </div>
  {/if}
</div>

<style>
  .onboarding-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }

  h1 {
    margin-bottom: 1.5rem;
  }

  .chat-container {
    height: 400px;
    overflow-y: auto;
    margin-bottom: 20px;
    padding: 10px;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: white;
  }

  .loading-wrapper {
    display: flex;
    justify-content: center;
    margin: 1rem 0;
  }

  .error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 1rem;
    border-radius: 4px;
    margin: 1rem 0;
  }

  .topic-input, .answer-input {
    background-color: white;
    padding: 1.5rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  }

  .topic-input h2 {
    margin-top: 0;
    margin-bottom: 1rem;
  }

  .description {
    color: #666;
    margin-bottom: 1.5rem;
  }

  .input-group {
    display: flex;
    gap: 10px;
  }

  input, textarea {
    flex: 1;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
    font-family: inherit;
  }

  textarea {
    resize: vertical;
    min-height: 100px;
    width: 100%;
  }

  .primary-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .primary-button:hover:not(:disabled) {
    background-color: #45a049;
  }

  .primary-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  .assessment-result {
    text-align: center;
    background-color: white;
    padding: 2rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  }

  .assessment-result h2 {
    color: #4CAF50;
    margin-top: 0;
  }

  @media (max-width: 768px) {
    .input-group {
      flex-direction: column;
    }

    .primary-button {
      width: 100%;
    }
  }
</style>