import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_URL,
});

// Request interceptor to add the auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password });
export const register = (username, email, password) => api.post('/auth/register', { username, email, password });

// Users
export const getMe = () => api.get('/users/me');
export const updateProfile = (data) => api.patch('/users/me', data);
export const changePassword = (data) => api.post('/users/me/change-password', data);
export const getUserByUsername = (username) => api.get(`/users/by-username/${username}`);

// Accounts (Platforms)
export const getAccounts = () => api.get('/accounts');
export const addAccount = (platform, handle) => api.post('/accounts', { platform, handle });
export const syncAccount = (id) => api.post(`/accounts/${id}/sync`);
export const syncAllAccounts = () => api.post('/accounts/sync-all');
export const deleteAccount = (id) => api.delete(`/accounts/${id}`);

// Analytics
export const getAnalytics = (userId) => api.get('/analytics', { params: userId ? { target_user_id: userId } : {} });
export const getRatingHistory = (params = {}) => api.get('/analytics/rating-history', { params });

export default api;
