import axios from 'axios';

// Production API URL for deployment
const API_URL = import.meta.env.VITE_API_URL || 'https://ecthr-translator.onrender.com/api';

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to all requests
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle 401 responses by redirecting to login
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Documents API
export const documentsApi = {
  upload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getStatus: async (documentId) => {
    const response = await client.get(`/documents/${documentId}`);
    return response.data;
  },

  download: async (documentId) => {
    const response = await client.get(`/documents/${documentId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

// Translation API
export const translationApi = {
  start: async (documentId, config = {}) => {
    const response = await client.post(`/translation/${documentId}/start`, {
      use_hudoc: config.useHudoc !== false,
      use_curia: config.useCuria !== false,
    });
    return response.data;
  },

  getStatus: async (documentId) => {
    const response = await client.get(`/translation/${documentId}/status`);
    return response.data;
  },

  finalize: async (documentId) => {
    const response = await client.post(`/translation/${documentId}/finalize`);
    return response.data;
  },

  connectWebSocket: (documentId, onMessage) => {
    const wsUrl = API_URL.replace('http', 'ws').replace('/api', '');
    const ws = new WebSocket(`${wsUrl}/api/translation/ws/${documentId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    return ws;
  },
};

// Glossary API
export const glossaryApi = {
  getTerms: async (documentId, params = {}) => {
    const response = await client.get(`/glossary/${documentId}`, { params });
    return response.data;
  },

  updateTerm: async (documentId, termId, update) => {
    const response = await client.put(`/glossary/${documentId}/${termId}`, update);
    return response.data;
  },

  applyTermToTranslation: async (documentId, termId) => {
    const response = await client.post(`/glossary/${documentId}/${termId}/apply-to-translation`);
    return response.data;
  },

  approveAll: async (documentId) => {
    const response = await client.post(`/glossary/${documentId}/approve-all`);
    return response.data;
  },
};

export default client;
