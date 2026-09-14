const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const TOKEN_STORAGE_KEY = 'quizipedia_token';

class ApiService {
  constructor() {
    this.baseURL = API_BASE;
    // Called when a request comes back 401 (missing/expired/invalid
    // token). AuthContext registers itself here so any request anywhere
    // in the app can trigger a clean logout, not just the login form.
    this.onUnauthorized = null;
  }

  getToken() {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  }

  setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const token = this.getToken();
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`API Error ${response.status}:`, errorText);

        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { detail: errorText || `HTTP ${response.status}` };
        }

        if (response.status === 401 && this.onUnauthorized) {
          this.onUnauthorized();
        }

        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log(`✅ API Response: ${url}`, data);
      return data;
    } catch (error) {
      console.error('❌ API request failed:', error);
      throw new Error(error.message || 'Network request failed');
    }
  }

  async signup(email, password) {
    const result = await this.request('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(result.access_token);
    return result;
  }

  async login(email, password) {
    const result = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    this.setToken(result.access_token);
    return result;
  }

  logout() {
    this.setToken(null);
  }

  async getMe() {
    return this.request('/auth/me');
  }

  async generateQuiz(url, options = {}) {
    const { questionCount, difficulty } = options;
    return this.request('/generate-quiz', {
      method: 'POST',
      body: JSON.stringify({
        url,
        ...(questionCount ? { question_count: questionCount } : {}),
        ...(difficulty ? { difficulty } : {}),
      }),
    });
  }

  async generateQuizFromFile(file, options = {}) {
    const { questionCount, difficulty } = options;
    // multipart/form-data upload -- deliberately NOT setting a
    // Content-Type header here; the browser sets it automatically with
    // the correct multipart boundary, and overriding it manually breaks
    // the upload.
    const token = this.getToken();
    const formData = new FormData();
    formData.append('file', file);
    if (questionCount) formData.append('question_count', String(questionCount));
    if (difficulty) formData.append('difficulty', difficulty);

    const response = await fetch(`${this.baseURL}/generate-quiz-from-file`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorData;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { detail: errorText || `HTTP ${response.status}` };
      }
      if (response.status === 401 && this.onUnauthorized) {
        this.onUnauthorized();
      }
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async submitQuizAttempt(quizId, attemptData) {
    return this.request(`/quizzes/${quizId}/attempt`, {
      method: 'POST',
      body: JSON.stringify(attemptData),
    });
  }

  async getQuizAttempts(quizId) {
    try {
      const result = await this.request(`/quizzes/${quizId}/attempts`);
      return result;
    } catch (error) {
      console.error(`Failed to get attempts for quiz ${quizId}:`, error);
      return [];
    }
  }

  async getQuizHistory() {
    return this.request('/quizzes');
  }

  async getQuizById(quizId) {
    return this.request(`/quizzes/${quizId}`);
  }

  async getHealth() {
    return this.request('/health');
  }
}

export const api = new ApiService();
