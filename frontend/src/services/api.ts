/**
 * API client with guest ID header injection
 */
import axios from 'axios';
import { getOrCreateGuestId } from '../utils/guestId';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Inject guest ID header on every request
apiClient.interceptors.request.use((config) => {
  const guestId = getOrCreateGuestId();
  config.headers['X-Guest-Id'] = guestId;
  return config;
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default apiClient;
