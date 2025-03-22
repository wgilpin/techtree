import axios from "axios";
import { user, saveUserToStorage, clearUserData } from "../stores/user";

// Use the proxy server URL instead of directly calling the backend
const API_URL = "/api";

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json"
  },
  // No need for withCredentials when using same-origin proxy
  withCredentials: false
});

// Log the API URL for debugging
console.log("Using proxy for API requests");

// Add a request interceptor to include auth token
api.interceptors.request.use(
  (config) => {
    let userData = null;
    user.subscribe(value => {
      userData = value;
    })();

    if (userData && userData.access_token) {
      config.headers.Authorization = `Bearer ${userData.access_token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor to handle authentication errors
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      // Handle token expiration
      clearUserData();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Authentication endpoints
export const auth = {
  login: async (email, password) => {
    try {
      console.log("API login called with email:", email);

      // Create a new axios instance for this specific request
      const loginAxios = axios.create({
        baseURL: API_URL,
        timeout: 30000,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        withCredentials: true // Enable credentials to match backend config
      });

      // Log request configuration before sending
      console.log("Login request config:", {
        url: `${API_URL}/auth/login`,
        method: "POST",
        data: new URLSearchParams({
          username: email,
          password: password
        }).toString()
      });

      // Make the request with the new axios instance
      const response = await loginAxios.post("/auth/login", new URLSearchParams({
        username: email,
        password: password
      }));

      console.log("Login response:", response);

      if (response.data) {
        // Update user store and save to localStorage
        saveUserToStorage({
          userId: response.data.user_id,
          email: response.data.email,
          name: response.data.name,
          access_token: response.data.access_token,
          isAuthenticated: true
        });
      }

      return response.data;
    } catch (error) {
      console.error("Login error:", error);
      console.error("Error response:", error.response);
      throw error;
    }
  },

  register: async (email, password, name) => {
    try {
      console.log("API register called with:", { email, name });

      // Create a new axios instance for this specific request
      const registerAxios = axios.create({
        baseURL: API_URL,
        timeout: 30000,
        headers: {
          "Content-Type": "application/json"
        },
        withCredentials: false
      });

      // Log request configuration before sending
      console.log("Request config:", {
        url: `${API_URL}/auth/register`,
        method: "POST",
        data: { email, password, name }
      });

      // Make the request with the new axios instance
      const response = await registerAxios.post("/auth/register", {
        email,
        password,
        name
      });

      console.log("Registration response:", response);

      if (response.data) {
        // Update user store and save to localStorage
        saveUserToStorage({
          userId: response.data.user_id,
          email: response.data.email,
          name: response.data.name,
          access_token: response.data.access_token,
          isAuthenticated: true
        });
      }

      return response.data;
    } catch (error) {
      console.error("Registration error in API service:", error);
      console.error("Error response:", error.response);
      throw error;
    }
  },

  logout: async () => {
    try {
      await api.post("/auth/logout");
      clearUserData();
      return { success: true };
    } catch (error) {
      console.error("Logout error:", error);
      clearUserData(); // Still clear data even if API fails
      throw error;
    }
  }
};

// Onboarding endpoints
export const onboarding = {
  startAssessment: async (topic) => {
    const response = await api.post("/onboarding/assessment", { topic });
    return response.data;
  },

  submitAnswer: async (answer) => {
    const response = await api.post("/onboarding/answer", { answer });
    return response.data;
  },

  getResult: async () => {
    const response = await api.get("/onboarding/result");
    return response.data;
  }
};

// Syllabus endpoints
export const syllabus = {
  create: async (topic, knowledge_level) => {
    const response = await api.post("/syllabus/create", { topic, knowledge_level });
    return response.data;
  },

  getById: async (syllabus_id) => {
    const response = await api.get(`/syllabus/${syllabus_id}`);
    return response.data;
  },

  getByTopicLevel: async (topic, level) => {
    const response = await api.get(`/syllabus/topic/${topic}/level/${level}`);
    return response.data;
  },

  getModuleDetails: async (syllabus_id, module_index) => {
    const response = await api.get(`/syllabus/${syllabus_id}/module/${module_index}`);
    return response.data;
  },

  getLessonSummary: async (syllabus_id, module_index, lesson_index) => {
    const response = await api.get(`/syllabus/${syllabus_id}/module/${module_index}/lesson/${lesson_index}`);
    return response.data;
  }
};

// Lesson endpoints
export const lesson = {
  getLesson: async (syllabus_id, module_index, lesson_index) => {
    const response = await api.get(`/lesson/${syllabus_id}/${module_index}/${lesson_index}`);
    return response.data;
  },

  getLessonById: async (lesson_id) => {
    const response = await api.get(`/lesson/by-id/${lesson_id}`);
    return response.data;
  },

  evaluateExercise: async (lesson_id, exercise_index, answer) => {
    const response = await api.post("/lesson/exercise/evaluate", {
      lesson_id,
      exercise_index,
      answer
    });
    return response.data;
  },

  updateProgress: async (syllabus_id, module_index, lesson_index, status) => {
    const response = await api.post("/lesson/progress", {
      syllabus_id,
      module_index,
      lesson_index,
      status
    });
    return response.data;
  }
};

// Progress tracking endpoints
export const progress = {
  getInProgressCourses: async () => {
    const response = await api.get("/progress/courses");
    return response.data;
  },

  getSyllabusProgress: async (syllabus_id) => {
    const response = await api.get(`/progress/syllabus/${syllabus_id}`);
    return response.data;
  },

  getRecentActivity: async () => {
    const response = await api.get("/progress/recent");
    return response.data;
  },

  getProgressSummary: async () => {
    const response = await api.get("/progress/summary");
    return response.data;
  }
};

export default {
  auth,
  onboarding,
  syllabus,
  lesson,
  progress
};