<script>
  import { onMount } from "svelte";
  import { navigate } from "svelte-routing";
  import { lesson as lessonApi } from "../services/api";
  import { sessionContext, user } from "../stores/user";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";

  export let syllabusId = null;
  export let module = 0;
  export let lesson = 0;

  let moduleIndex = parseInt(module, 10) || 0;
  let lessonIndex = parseInt(lesson, 10) || 0;

  let lessonData = null;
  let isLoading = true;
  let error = null;
  let isRetrying = false;

  // Exercise state
  let currentExerciseIndex = 0;
  let userAnswer = "";
  let exerciseResult = null;
  let isEvaluating = false;

  // For navigation
  let totalModules = 0;
  let totalLessonsInModule = 0;

  onMount(async () => {
    if (!$user.isAuthenticated) {
      navigate("/login");
      return;
    }
    if (!syllabusId) {
      error = "Missing syllabus ID. Please start from the syllabus page.";
      isLoading = false;
      return;
    }

    await loadLesson();

    // If user is authenticated, mark lesson as in progress
    if ($user.isAuthenticated) {
      try {
        await lessonApi.updateProgress(syllabusId, moduleIndex, lessonIndex, "in_progress");
      } catch (err) {
        console.error("Error updating progress:", err);
        // Continue even if progress update fails
      }
    }
  });

  async function loadLesson() {
    try {
      isLoading = true;
      error = null;
      exerciseResult = null;

      // Fetch lesson data
      const result = await lessonApi.getLesson(syllabusId, moduleIndex, lessonIndex);
      lessonData = result;

      // Update session context
      sessionContext.update(ctx => ({
        ...ctx,
        currentSyllabusId: syllabusId,
        currentModuleTitle: lessonData.content.module_title,
        currentLessonTitle: lessonData.content.title
      }));

      // Reset exercise state
      currentExerciseIndex = 0;
      userAnswer = "";

      // Set navigation data (for now with placeholder values)
      // In a real implementation, you would get this from the syllabus
      totalModules = 5; // Placeholder
      totalLessonsInModule = 5; // Placeholder
    } catch (err) {
      console.error("Error fetching lesson:", err);
      error = err.response?.data?.detail || `Failed to load the lesson: ${err.message || 'Unknown error'}`;
    } finally {
      isLoading = false;
    }
  }

  async function evaluateExercise() {
    if (!userAnswer.trim()) return;

    try {
      isEvaluating = true;

      const result = await lessonApi.evaluateExercise(
        lessonData.lesson_id,
        currentExerciseIndex,
        userAnswer
      );

      exerciseResult = result;

      // If this is the last exercise and the user is authenticated, mark as completed
      if (
        $user.isAuthenticated &&
        currentExerciseIndex === lessonData.content.exercises.length - 1
      ) {
        try {
          await lessonApi.updateProgress(syllabusId, moduleIndex, lessonIndex, "completed");
        } catch (err) {
          console.error("Error updating progress:", err);
        }
      }
    } catch (err) {
      console.error("Error evaluating exercise:", err);
      error = err.response?.data?.detail || `Failed to evaluate your answer: ${err.message || 'Unknown error'}`;
    } finally {
      isEvaluating = false;
    }
  }

  function moveToNextExercise() {
    if (currentExerciseIndex < lessonData.content.exercises.length - 1) {
      currentExerciseIndex++;
      userAnswer = "";
      exerciseResult = null;
    }
  }

  function moveToPreviousExercise() {
    if (currentExerciseIndex > 0) {
      currentExerciseIndex--;
      userAnswer = "";
      exerciseResult = null;
    }
  }

  function navigateToNextLesson() {
    if (lessonIndex < totalLessonsInModule - 1) {
      navigate(`/lesson/${syllabusId}/${moduleIndex}/${lessonIndex + 1}`);
    } else if (moduleIndex < totalModules - 1) {
      navigate(`/lesson/${syllabusId}/${moduleIndex + 1}/0`);
    } else {
      // Return to syllabus if this is the last lesson
      navigate(`/syllabus/${$sessionContext.currentTopic}/${$sessionContext.currentLevel}`);
    }
  }

  function navigateToPreviousLesson() {
    if (lessonIndex > 0) {
      navigate(`/lesson/${syllabusId}/${moduleIndex}/${lessonIndex - 1}`);
    } else if (moduleIndex > 0) {
      // Need to determine the last lesson in the previous module
      // For this example, we'll assume 5 lessons in each module
      navigate(`/lesson/${syllabusId}/${moduleIndex - 1}/4`);
    } else {
      // Return to syllabus if this is the first lesson
      navigate(`/syllabus/${$sessionContext.currentTopic}/${$sessionContext.currentLevel}`);
    }
  }

  async function retryLoadLesson() {
    isRetrying = true;
    await loadLesson();
    isRetrying = false;
  }

  function navigateToSyllabus() {
    navigate(`/syllabus/${$sessionContext.currentTopic}/${$sessionContext.currentLevel}`);
  }
</script>

<div class="lesson-container">
  <div class="lesson-navigation">
    <button class="nav-button" on:click={navigateToSyllabus}>
      ← Back to Syllabus
    </button>

    <div class="lesson-info">
      {#if lessonData && lessonData.content}
        <span>Module {moduleIndex + 1}: {lessonData.content.module_title}</span>
        <span class="separator">›</span>
        <span>Lesson {lessonIndex + 1}: {lessonData.content.title}</span>
      {:else}
        <span>Loading lesson...</span>
      {/if}
    </div>

    <div class="lesson-navigation-buttons">
      <button
        class="nav-button"
        on:click={navigateToPreviousLesson}
        disabled={moduleIndex === 0 && lessonIndex === 0}
      >
        ← Previous
      </button>
      <button
        class="nav-button"
        on:click={navigateToNextLesson}
      >
        Next →
      </button>
    </div>
  </div>

  {#if isLoading}
    <div class="lesson-content-container">
      <LoadingIndicator message="Loading lesson content..." />
    </div>
  {:else if error}
    <div class="lesson-content-container">
      <div class="error-message">
        {error}
        {#if !isLoading}
          <button class="retry-button" on:click={retryLoadLesson} disabled={isRetrying}>
            {isRetrying ? 'Retrying...' : 'Retry'}
          </button>
        {/if}
      </div>
    </div>
  {:else if lessonData}
    <div class="lesson-content-container">
      <div class="lesson-content">
        <h1>{lessonData.content.title}</h1>

        {#if lessonData.content.overview}
          <div class="lesson-overview">
            <h2>Overview</h2>
            <p>{lessonData.content.overview}</p>
          </div>
        {/if}

        {#if lessonData.content.sections}
          {#each lessonData.content.sections as section}
            <div class="lesson-section">
              <h2>{section.title}</h2>
              {#each section.content.split('\n\n') as paragraph}
                <p>{paragraph}</p>
              {/each}

              {#if section.examples && section.examples.length > 0}
                <div class="examples">
                  {#each section.examples as example}
                    <div class="example">
                      <h4>Example: {example.title}</h4>
                      {#if example.code}
                        <pre><code>{example.code}</code></pre>
                      {/if}
                      <p>{example.explanation}</p>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
        {/if}

        {#if lessonData.content.exercises && lessonData.content.exercises.length > 0}
          <div class="exercises-section">
            <h2>Practice Exercises</h2>

            <div class="exercise-navigation">
              <button
                class="exercise-nav-button"
                on:click={moveToPreviousExercise}
                disabled={currentExerciseIndex === 0}
              >
                ← Previous
              </button>
              <span>Exercise {currentExerciseIndex + 1} of {lessonData.content.exercises.length}</span>
              <button
                class="exercise-nav-button"
                on:click={moveToNextExercise}
                disabled={currentExerciseIndex === lessonData.content.exercises.length - 1 || !exerciseResult}
              >
                Next →
              </button>
            </div>

            <div class="exercise">
              <h3>Exercise {currentExerciseIndex + 1}</h3>
              <p class="exercise-question">
                {lessonData.content.exercises[currentExerciseIndex].question}
              </p>

              {#if lessonData.content.exercises[currentExerciseIndex].hints}
                <div class="hints">
                  <details>
                    <summary>Hint</summary>
                    <p>{lessonData.content.exercises[currentExerciseIndex].hints}</p>
                  </details>
                </div>
              {/if}

              <div class="exercise-input">
                <textarea
                  bind:value={userAnswer}
                  placeholder="Enter your answer here..."
                  rows="5"
                  disabled={isEvaluating || exerciseResult}
                ></textarea>

                {#if !exerciseResult}
                  <button
                    class="submit-button"
                    on:click={evaluateExercise}
                    disabled={isEvaluating || !userAnswer.trim()}
                  >
                    {isEvaluating ? 'Evaluating...' : 'Submit Answer'}
                  </button>
                {/if}
              </div>

              {#if exerciseResult}
                <div class="exercise-result {exerciseResult.is_correct ? 'correct' : 'incorrect'}">
                  <div class="result-header">
                    {#if exerciseResult.is_correct}
                      <span class="icon">✓</span> Correct!
                    {:else}
                      <span class="icon">✗</span> Not quite right.
                    {/if}
                  </div>

                  <div class="feedback">
                    <p>{exerciseResult.feedback}</p>

                    {#if exerciseResult.explanation}
                      <div class="explanation">
                        <h4>Explanation:</h4>
                        <p>{exerciseResult.explanation}</p>
                      </div>
                    {/if}
                  </div>

                  {#if currentExerciseIndex < lessonData.content.exercises.length - 1}
                    <button class="next-exercise-button" on:click={moveToNextExercise}>
                      Next Exercise →
                    </button>
                  {:else}
                    <button class="complete-button" on:click={navigateToNextLesson}>
                      Complete Lesson & Continue
                    </button>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        {/if}

        {#if lessonData.content.summary}
          <div class="lesson-summary">
            <h2>Summary</h2>
            <p>{lessonData.content.summary}</p>
          </div>
        {/if}

        {#if lessonData.content.next_steps}
          <div class="next-steps">
            <h2>Next Steps</h2>
            <p>{lessonData.content.next_steps}</p>
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <div class="lesson-content-container">
      <div class="error-message">No lesson data found.</div>
    </div>
  {/if}
</div>

<style>
  .lesson-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 20px;
  }

  .lesson-navigation {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .lesson-info {
    font-size: 0.9rem;
    color: #666;
  }

  .separator {
    margin: 0 0.5rem;
  }

  .nav-button {
    background-color: #f1f1f1;
    color: #333;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .nav-button:hover:not(:disabled) {
    background-color: #e7e7e7;
  }

  .nav-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .lesson-content-container {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    padding: 2rem;
  }

  .lesson-content h1 {
    margin-top: 0;
    color: #333;
    font-size: 1.8rem;
  }

  .lesson-overview {
    background-color: #f9f9f9;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
  }

  .lesson-section {
    margin-bottom: 2.5rem;
  }

  .lesson-section h2 {
    color: #333;
    border-bottom: 2px solid #f0f0f0;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
  }

  .lesson-section p {
    line-height: 1.6;
    margin-bottom: 1rem;
  }

  .examples {
    margin-top: 1.5rem;
  }

  .example {
    background-color: #f5f5f5;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .example h4 {
    margin-top: 0;
    color: #333;
    margin-bottom: 1rem;
  }

  pre {
    background-color: #f1f1f1;
    padding: 1rem;
    border-radius: 4px;
    overflow-x: auto;
    margin-bottom: 1rem;
  }

  code {
    font-family: monospace;
  }

  .exercises-section {
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 2px dashed #eee;
  }

  .exercise-navigation {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .exercise-nav-button {
    background-color: #f1f1f1;
    color: #333;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .exercise-nav-button:hover:not(:disabled) {
    background-color: #e7e7e7;
  }

  .exercise-nav-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .exercise {
    background-color: #f9f9f9;
    padding: 1.5rem;
    border-radius: 8px;
  }

  .exercise-question {
    font-weight: 500;
    margin-bottom: 1.5rem;
  }

  .hints {
    margin-bottom: 1.5rem;
  }

  details {
    padding: 0.5rem;
    border: 1px solid #ddd;
    border-radius: 4px;
  }

  summary {
    cursor: pointer;
    color: #2196f3;
    font-weight: 500;
  }

  .exercise-input {
    margin-bottom: 1.5rem;
  }

  textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
    font-family: inherit;
    margin-bottom: 1rem;
  }

  .submit-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .submit-button:hover:not(:disabled) {
    background-color: #45a049;
  }

  .submit-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  .exercise-result {
    padding: 1.5rem;
    border-radius: 8px;
    margin-top: 1.5rem;
  }

  .correct {
    background-color: #e8f5e9;
    border-left: 5px solid #4CAF50;
  }

  .incorrect {
    background-color: #ffebee;
    border-left: 5px solid #f44336;
  }

  .result-header {
    display: flex;
    align-items: center;
    font-weight: bold;
    font-size: 1.1rem;
    margin-bottom: 1rem;
  }

  .icon {
    margin-right: 0.5rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    color: white;
  }

  .correct .icon {
    background-color: #4CAF50;
  }

  .incorrect .icon {
    background-color: #f44336;
  }

  .feedback {
    margin-bottom: 1.5rem;
  }

  .explanation {
    background-color: rgba(255, 255, 255, 0.5);
    padding: 1rem;
    border-radius: 4px;
  }

  .explanation h4 {
    margin-top: 0;
    margin-bottom: 0.5rem;
  }

  .next-exercise-button, .complete-button {
    background-color: #2196f3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .next-exercise-button:hover, .complete-button:hover {
    background-color: #1976d2;
  }

  .complete-button {
    background-color: #4CAF50;
  }

  .complete-button:hover {
    background-color: #45a049;
  }

  .lesson-summary, .next-steps {
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 2px dashed #eee;
  }

  .error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 1rem;
    border-radius: 4px;
    margin: 1rem 0;
  }

  @media (max-width: 768px) {
    .lesson-navigation, .exercise-navigation {
      flex-direction: column;
      align-items: flex-start;
    }

    .lesson-navigation-buttons {
      display: flex;
      gap: 1rem;
      width: 100%;
    }

    .lesson-navigation-buttons .nav-button {
      flex: 1;
    }
  }

  .retry-button {
    background-color: #2196f3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    margin-top: 0.5rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .retry-button:hover:not(:disabled) {
    background-color: #1976d2;
  }

  .retry-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
</style>