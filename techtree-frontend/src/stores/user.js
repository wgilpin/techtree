import { writable } from "svelte/store";

// User authentication and profile
export const user = writable({
  userId: null,
  email: null,
  name: null,
  isAuthenticated: false
});

// Current session context
export const sessionContext = writable({
  currentTopic: null,
  currentLevel: null,
  currentSyllabusId: null,
  currentModuleTitle: null,
  currentLessonTitle: null
});

// Progress tracking
export const userProgress = writable({
  topics: {},
  completedLessons: [],
  assessmentResults: {}
});

// Message history for chat-like interfaces
export const messageHistory = writable([]);

// Save user to localStorage
export function saveUserToStorage(userData) {
  if (typeof window !== 'undefined') {
    localStorage.setItem("techtree_user", JSON.stringify(userData));
    user.set(userData);
  }
}

// Load user from localStorage
export function loadUserFromStorage() {
  if (typeof window !== 'undefined') {
    const storedUser = localStorage.getItem("techtree_user");
    if (storedUser) {
      user.set(JSON.parse(storedUser));
      return true;
    }
  }
  return false;
}

// Clear user data on logout
export function clearUserData() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem("techtree_user");
    user.set({
      userId: null,
      email: null,
      name: null,
      isAuthenticated: false
    });
    sessionContext.set({
      currentTopic: null,
      currentLevel: null,
      currentSyllabusId: null,
      currentModuleTitle: null,
      currentLessonTitle: null
    });
    userProgress.set({
      topics: {},
      completedLessons: [],
      assessmentResults: {}
    });
    messageHistory.set([]);
  }
}