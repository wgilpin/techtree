<script>
  import { onMount } from "svelte";
  import { user, loadUserFromStorage } from "../stores/user";
  import { progress } from "../services/api";
  import LoadingIndicator from "../components/common/LoadingIndicator.svelte";
  import { navigate } from "svelte-routing";

  let inProgressCourses = [];
  let recentActivity = [];
  let summaryStats = null;
  let isLoading = true;
  let error = null;

  onMount(async () => {
    // Check if the user is logged in
    if (!$user.isAuthenticated) {
      navigate("/login");
      return;
    }

    try {
      isLoading = true;

      // Fetch in-progress courses, recent activity, and summary stats
      const [coursesData, recentData, statsData] = await Promise.all([
        progress.getInProgressCourses(),
        progress.getRecentActivity(),
        progress.getProgressSummary()
      ]);

      inProgressCourses = coursesData || [];
      recentActivity = recentData || [];
      summaryStats = statsData || {};
    } catch (err) {
      console.error("Error fetching dashboard data:", err);
      error = "Could not load your dashboard data. Please try again later.";
    } finally {
      isLoading = false;
    }
  });

  function startNewTopic() {
    navigate("/onboard");
  }

  function continueCourse(syllabusId, moduleIndex = 0, lessonIndex = 0) {
    navigate(`/lesson/${syllabusId}/${moduleIndex}/${lessonIndex}`);
  }
</script>

<div class="dashboard">
  <div class="dashboard-header">
    <h1>Welcome{$user.name ? `, ${$user.name}` : ""}!</h1>
    <button class="primary-button" on:click={startNewTopic}>Start New Topic</button>
  </div>

  {#if isLoading}
    <LoadingIndicator message="Loading your dashboard..." />
  {:else if error}
    <div class="error-message">{error}</div>
  {:else}
    <div class="dashboard-content">
      <!-- Progress Summary -->
      {#if $user.isAuthenticated && summaryStats}
        <section class="stats-section">
          <h2>Your Learning Progress</h2>
          <div class="stats-grid">
            <div class="stat-card">
              <div class="stat-value">{summaryStats.total_topics || 0}</div>
              <div class="stat-label">Topics Explored</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{summaryStats.completed_lessons || 0}</div>
              <div class="stat-label">Lessons Completed</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{Math.round(summaryStats.avg_lesson_score * 100) || 0}%</div>
              <div class="stat-label">Avg. Exercise Score</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{summaryStats.assessments_taken || 0}</div>
              <div class="stat-label">Assessments Taken</div>
            </div>
          </div>
        </section>
      {/if}

      <!-- In-Progress Courses -->
      <section>
        <h2>In-Progress Courses</h2>
        {#if inProgressCourses.length > 0}
          <div class="course-grid">
            {#each inProgressCourses as course}
              <div class="course-card">
                <div class="course-info">
                  <h3>{course.topic}</h3>
                  <div class="course-level">{course.level}</div>
                  <div class="progress-bar">
                    <div class="progress-fill" style="width: {course.progress_percentage}%"></div>
                  </div>
                  <div class="progress-text">
                    {course.completed_lessons} of {course.total_lessons} lessons completed
                  </div>
                </div>
                <button
                  class="continue-button"
                  on:click={() => continueCourse(course.syllabus_id)}
                >
                  Continue
                </button>
              </div>
            {/each}
          </div>
        {:else}
          <div class="empty-state">
            <p>You don't have any courses in progress.</p>
            <button class="secondary-button" on:click={startNewTopic}>
              Start Learning
            </button>
          </div>
        {/if}
      </section>

      <!-- Recent Activity -->
      {#if $user.isAuthenticated && recentActivity.length > 0}
        <section>
          <h2>Recent Activity</h2>
          <div class="activity-list">
            {#each recentActivity as activity}
              <div class="activity-item">
                <div class="activity-icon">
                  {#if activity.status === "completed"}
                    <span class="icon-completed">✓</span>
                  {:else if activity.status === "in_progress"}
                    <span class="icon-in-progress">▶</span>
                  {:else}
                    <span class="icon-not-started">○</span>
                  {/if}
                </div>
                <div class="activity-content">
                  <div class="activity-title">
                    {activity.topic} - {activity.module_title}
                  </div>
                  <div class="activity-subtitle">
                    {activity.lesson_title}
                  </div>
                  <div class="activity-date">
                    {new Date(activity.updated_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  class="continue-button small"
                  on:click={() => continueCourse(
                    activity.syllabus_id,
                    activity.module_index,
                    activity.lesson_index
                  )}
                >
                  Continue
                </button>
              </div>
            {/each}
          </div>
        </section>
      {/if}

      <!-- Featured Topics -->
      <section>
        <h2>Featured Topics</h2>
        <div class="topic-grid">
          {#each ["Machine Learning", "Web Development", "Cybersecurity", "Data Science"] as topic}
            <div class="topic-card">
              <h3>{topic}</h3>
              <button
                class="secondary-button"
                on:click={() => navigate(`/onboard/${encodeURIComponent(topic)}`)}
              >
                Explore
              </button>
            </div>
          {/each}
        </div>
      </section>
    </div>
  {/if}
</div>

<style>
  .dashboard {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
  }

  .dashboard-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
  }

  .dashboard-content {
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  section {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    padding: 1.5rem;
  }

  h1 {
    font-size: 2rem;
    margin: 0;
  }

  h2 {
    font-size: 1.5rem;
    margin-top: 0;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid #f0f0f0;
    padding-bottom: 0.5rem;
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

  .primary-button:hover {
    background-color: #45a049;
  }

  .secondary-button {
    background-color: #f1f1f1;
    color: #333;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .secondary-button:hover {
    background-color: #e7e7e7;
  }

  .error-message {
    background-color: #ffebee;
    color: #c62828;
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .stat-card {
    background-color: #f9f9f9;
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
  }

  .stat-value {
    font-size: 2rem;
    font-weight: bold;
    color: #4CAF50;
    margin-bottom: 0.5rem;
  }

  .stat-label {
    color: #666;
  }

  .course-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
  }

  .course-card {
    background-color: #f9f9f9;
    border-radius: 8px;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.3s, box-shadow 0.3s;
  }

  .course-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
  }

  .course-info {
    margin-bottom: 1.5rem;
  }

  .course-card h3 {
    margin-top: 0;
    margin-bottom: 0.5rem;
  }

  .course-level {
    display: inline-block;
    background-color: #e0f2f1;
    color: #00897b;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    margin-bottom: 1rem;
  }

  .progress-bar {
    height: 8px;
    background-color: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-fill {
    height: 100%;
    background-color: #4CAF50;
  }

  .progress-text {
    font-size: 0.9rem;
    color: #666;
  }

  .continue-button {
    align-self: flex-end;
    background-color: #2196f3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: background-color 0.3s;
  }

  .continue-button:hover {
    background-color: #1976d2;
  }

  .continue-button.small {
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
  }

  .empty-state {
    text-align: center;
    padding: 2rem;
    color: #666;
  }

  .activity-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .activity-item {
    display: flex;
    align-items: center;
    background-color: #f9f9f9;
    padding: 1rem;
    border-radius: 8px;
  }

  .activity-icon {
    margin-right: 1rem;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    font-weight: bold;
  }

  .icon-completed {
    background-color: #4CAF50;
    color: white;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-in-progress {
    background-color: #2196f3;
    color: white;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .icon-not-started {
    border: 2px solid #9e9e9e;
    color: #9e9e9e;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .activity-content {
    flex: 1;
  }

  .activity-title {
    font-weight: bold;
  }

  .activity-subtitle {
    font-size: 0.9rem;
    color: #666;
  }

  .activity-date {
    font-size: 0.8rem;
    color: #999;
  }

  .topic-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
  }

  .topic-card {
    background-color: #f9f9f9;
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
    transition: transform 0.3s, box-shadow 0.3s;
  }

  .topic-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
  }

  .topic-card h3 {
    margin-top: 0;
    margin-bottom: 1rem;
  }

  @media (max-width: 768px) {
    .dashboard-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }

    .stats-grid, .course-grid, .topic-grid {
      grid-template-columns: 1fr;
    }
  }
</style>