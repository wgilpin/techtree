<script>
  import { onMount } from "svelte";
  import { navigate } from "svelte-routing";
  import { syllabus as syllabusApi, progress } from "../services/api";
  import { sessionContext, user } from "../stores/user";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";

  export let topic = null;
  export let level = null;

  let syllabusData = null;
  let isLoading = true;
  let error = null;
  let progressData = {};

  onMount(async () => {
    if (!$user.isAuthenticated) {
      navigate("/login");
      return;
    }
    if (!topic || !level) {
      error = "Missing topic or knowledge level. Please start from the assessment.";
      isLoading = false;
      return;
    }

    try {
      isLoading = true;
      error = null;

      // Update session context
      sessionContext.update(ctx => ({
        ...ctx,
        currentTopic: topic,
        currentLevel: level
      }));

      // Fetch syllabus data
      const result = await syllabusApi.getByTopicLevel(topic, level);
      syllabusData = result;

      // Update session context with syllabus ID
      sessionContext.update(ctx => ({
        ...ctx,
        currentSyllabusId: result.syllabus_id
      }));

      // If user is logged in, fetch progress data
      if ($user.isAuthenticated) {
        try {
          const progressResult = await progress.getSyllabusProgress(result.syllabus_id);

          // Convert array of progress items to a map for easy lookup
          progressData = progressResult.reduce((acc, item) => {
            const key = `${item.module_index}-${item.lesson_index}`;
            acc[key] = item.status;
            return acc;
          }, {});
        } catch (progressErr) {
          console.error("Error fetching progress data:", progressErr);
          // Continue even if progress data fails to load
        }
      }
    } catch (err) {
      console.error("Error fetching syllabus:", err);
      error = "Failed to load the syllabus. Please try again.";
    } finally {
      isLoading = false;
    }
  });

  function startLesson(moduleIndex, lessonIndex, moduleTitle, lessonTitle) {
    // Update session context with current module and lesson titles
    sessionContext.update(ctx => ({
      ...ctx,
      currentModuleTitle: moduleTitle,
      currentLessonTitle: lessonTitle
    }));

    // Navigate to the lesson page
    navigate(`/lesson/${syllabusData.syllabus_id}/${moduleIndex}/${lessonIndex}`);
  }

  function getLessonStatusClass(moduleIndex, lessonIndex) {
    const key = `${moduleIndex}-${lessonIndex}`;
    const status = progressData[key] || "not_started";

    switch(status) {
      case "completed":
        return "completed";
      case "in_progress":
        return "in-progress";
      default:
        return "not-started";
    }
  }

  function getLessonStatusIcon(moduleIndex, lessonIndex) {
    const key = `${moduleIndex}-${lessonIndex}`;
    const status = progressData[key] || "not_started";

    switch(status) {
      case "completed":
        return "✓";
      case "in_progress":
        return "▶";
      default:
        return "";
    }
  }
</script>

<div class="syllabus-container">
  <div class="syllabus-header">
    <h1>Personalized Syllabus</h1>
    <div class="syllabus-details">
      <div class="topic-badge">{topic}</div>
      <div class="level-badge">{level}</div>
    </div>
  </div>

  {#if isLoading}
    <LoadingIndicator message="Loading your personalized syllabus..." />
  {:else if error}
    <div class="error-message">{error}</div>
  {:else if syllabusData}
    <div class="syllabus-content">
      <div class="syllabus-description">
        <h2>{syllabusData.content.title}</h2>
        <p>{syllabusData.content.description}</p>

        {#if syllabusData.is_new}
          <div class="info-box">
            <p>
              <strong>A personalized syllabus has been created just for you!</strong>
              This syllabus is tailored to your knowledge level and learning goals.
            </p>
          </div>
        {/if}
      </div>

      <div class="modules-container">
        {#each syllabusData.content.modules as module, moduleIndex}
          <div class="module-card">
            <div class="module-header">
              <h3>Module {moduleIndex + 1}: {module.title}</h3>
              <p>{module.summary}</p>
            </div>

            <div class="lessons-list">
              {#each module.lessons as lesson, lessonIndex}
                <div class="lesson-item {getLessonStatusClass(moduleIndex, lessonIndex)}">
                  <div class="lesson-status-icon">
                    {getLessonStatusIcon(moduleIndex, lessonIndex)}
                  </div>
                  <div class="lesson-info">
                    <div class="lesson-title">
                      Lesson {lessonIndex + 1}: {lesson.title}
                    </div>
                    {#if lesson.duration}
                      <div class="lesson-duration">{lesson.duration}</div>
                    {/if}
                    {#if lesson.summary}
                      <div class="lesson-summary">{lesson.summary}</div>
                    {/if}
                  </div>
                  <button
                    class="start-button"
                    on:click={() => startLesson(
                      moduleIndex,
                      lessonIndex,
                      module.title,
                      lesson.title
                    )}
                  >
                    {progressData[`${moduleIndex}-${lessonIndex}`] === "completed"
                      ? "Review"
                      : progressData[`${moduleIndex}-${lessonIndex}`] === "in_progress"
                        ? "Continue"
                        : "Start"}
                  </button>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <div class="error-message">No syllabus data found.</div>
  {/if}
</div>

<style>
  .syllabus-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
  }

  .syllabus-header {
    margin-bottom: 2rem;
  }

  .syllabus-details {
    display: flex;
    gap: 10px;
    margin-top: 0.5rem;
  }

  .topic-badge, .level-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.9rem;
  }

  .topic-badge {
    background-color: #e3f2fd;
    color: #1565c0;
  }

  .level-badge {
    background-color: #e8f5e9;
    color: #2e7d32;
  }

  .error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 1rem;
    border-radius: 4px;
    margin: 1rem 0;
  }

  .syllabus-content {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  .syllabus-description {
    background-color: white;
    padding: 1.5rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  }

  .syllabus-description h2 {
    margin-top: 0;
    color: #333;
  }

  .info-box {
    background-color: #e3f2fd;
    padding: 1rem;
    border-radius: 4px;
    border-left: 4px solid #1565c0;
    margin-top: 1rem;
  }

  .info-box p {
    margin: 0;
  }

  .modules-container {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .module-card {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    overflow: hidden;
  }

  .module-header {
    padding: 1.5rem;
    background-color: #f5f5f5;
  }

  .module-header h3 {
    margin-top: 0;
    margin-bottom: 0.5rem;
    color: #333;
  }

  .module-header p {
    margin: 0;
    color: #666;
  }

  .lessons-list {
    padding: 1rem;
  }

  .lesson-item {
    display: flex;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #eee;
    transition: background-color 0.3s;
  }

  .lesson-item:last-child {
    border-bottom: none;
  }

  .lesson-item:hover {
    background-color: #f9f9f9;
  }

  .lesson-status-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 1rem;
    font-weight: bold;
  }

  .completed .lesson-status-icon {
    background-color: #4CAF50;
    color: white;
  }

  .in-progress .lesson-status-icon {
    background-color: #2196f3;
    color: white;
  }

  .not-started .lesson-status-icon {
    border: 2px solid #9e9e9e;
    color: #9e9e9e;
    width: 20px;
    height: 20px;
  }

  .lesson-info {
    flex: 1;
  }

  .lesson-title {
    font-weight: bold;
    margin-bottom: 0.25rem;
  }

  .lesson-duration {
    font-size: 0.8rem;
    color: #666;
    margin-bottom: 0.25rem;
  }

  .lesson-summary {
    font-size: 0.9rem;
    color: #666;
  }

  .start-button {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .start-button:hover {
    background-color: #45a049;
  }

  .completed .start-button {
    background-color: #9e9e9e;
  }

  .completed .start-button:hover {
    background-color: #757575;
  }

  @media (max-width: 768px) {
    .lesson-item {
      flex-direction: column;
      align-items: flex-start;
    }

    .lesson-status-icon {
      margin-right: 0;
      margin-bottom: 0.5rem;
    }

    .lesson-info {
      margin-bottom: 1rem;
      width: 100%;
    }

    .start-button {
      align-self: flex-end;
    }
  }
</style>