// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://ecthr-translator.onrender.com/api';

// WebSocket URL (derived from API URL)
export const WS_BASE_URL = API_BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://').replace('/api', '');

// Get auth token from localStorage
export function getAuthToken() {
  return localStorage.getItem('auth_token');
}

// Get auth headers for API calls
export function getAuthHeaders() {
  const token = getAuthToken();
  if (token) {
    return { 'Authorization': `Bearer ${token}` };
  }
  return {};
}

// Authenticated fetch wrapper
export async function authFetch(url, options = {}) {
  const headers = {
    ...getAuthHeaders(),
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // If unauthorized, redirect to login
  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
    throw new Error('Authentication required');
  }

  return response;
}
