import React, { useState, useEffect, createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import HomePage from './pages/HomePage';
import TranslationPage from './pages/TranslationPage';
import LoginPage from './pages/LoginPage';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const queryClient = new QueryClient();

// Auth context
const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

// Get auth token for API calls
export function getAuthToken() {
  return localStorage.getItem('auth_token');
}

// Get auth headers for fetch calls
export function getAuthHeaders() {
  const token = getAuthToken();
  if (token) {
    return { 'Authorization': `Bearer ${token}` };
  }
  return {};
}

// Protected route wrapper
function ProtectedRoute({ children, isAuthenticated, authRequired }) {
  if (authRequired && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [loading, setLoading] = useState(true);

  // Check auth status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      // First check if auth is required
      const statusResponse = await authFetch(`${API_BASE_URL}/api/auth/status`);
      const statusData = await statusResponse.json();

      if (!statusData.auth_required) {
        // No auth required
        setAuthRequired(false);
        setIsAuthenticated(true);
        setLoading(false);
        return;
      }

      setAuthRequired(true);

      // Check if we have a valid token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      // Verify token
      const verifyResponse = await authFetch(`${API_BASE_URL}/api/auth/verify`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const verifyData = await verifyResponse.json();

      setIsAuthenticated(verifyData.valid);
      if (!verifyData.valid) {
        localStorage.removeItem('auth_token');
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      // If server is down, assume not authenticated
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (token) => {
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        await authFetch(`${API_BASE_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      } catch (error) {
        console.error('Logout error:', error);
      }
    }
    localStorage.removeItem('auth_token');
    setIsAuthenticated(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, authRequired, handleLogout }}>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Routes>
            <Route
              path="/login"
              element={
                isAuthenticated && authRequired ? (
                  <Navigate to="/" replace />
                ) : (
                  <LoginPage onLogin={handleLogin} />
                )
              }
            />
            <Route
              path="/"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated} authRequired={authRequired}>
                  <HomePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/translation/:documentId"
              element={
                <ProtectedRoute isAuthenticated={isAuthenticated} authRequired={authRequired}>
                  <TranslationPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </QueryClientProvider>
    </AuthContext.Provider>
  );
}

export default App;
