import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import { AuthContext } from './authContextObject';

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  // Starts true: on first load we don't yet know if a stored token is
  // valid, so the app should show a loading state rather than briefly
  // flashing the login screen before the /auth/me check resolves.
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  useEffect(() => {
    // Any 401 from anywhere in the app (not just the login form -- e.g.
    // a token that expires mid-session) should cleanly log the user out
    // rather than leave them staring at a broken screen.
    api.onUnauthorized = () => {
      api.logout();
      setUser(null);
    };
    return () => {
      api.onUnauthorized = null;
    };
  }, []);

  useEffect(() => {
    const validateStoredToken = async () => {
      if (!api.getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await api.getMe();
        setUser(me);
      } catch {
        // Stored token is invalid/expired -- clear it rather than keep
        // retrying on every request.
        api.logout();
      } finally {
        setLoading(false);
      }
    };
    validateStoredToken();
  }, []);

  const signup = useCallback(async (email, password) => {
    setAuthError(null);
    try {
      const result = await api.signup(email, password);
      setUser(result.user);
      return true;
    } catch (err) {
      setAuthError(err.message || 'Signup failed');
      return false;
    }
  }, []);

  const login = useCallback(async (email, password) => {
    setAuthError(null);
    try {
      const result = await api.login(email, password);
      setUser(result.user);
      return true;
    } catch (err) {
      setAuthError(err.message || 'Login failed');
      return false;
    }
  }, []);

  const value = {
    user,
    loading,
    authError,
    isAuthenticated: !!user,
    signup,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
