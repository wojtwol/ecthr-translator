// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://ecthr-translator-backend.onrender.com/api';

// WebSocket URL (derived from API URL)
export const WS_BASE_URL = API_BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://').replace('/api', '');
