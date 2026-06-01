import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore } from '@/stores/auth';

describe('Auth Store', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset store state
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
  });

  it('has correct initial state', () => {
    const state = useAuthStore.getState();
    
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it('setTokens stores tokens correctly', () => {
    const { setTokens } = useAuthStore.getState();
    
    setTokens('access_token_123', 'refresh_token_456');
    
    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('access_token_123');
    expect(state.refreshToken).toBe('refresh_token_456');
    expect(state.isAuthenticated).toBe(true);
    expect(localStorage.getItem('access_token')).toBe('access_token_123');
    expect(localStorage.getItem('refresh_token')).toBe('refresh_token_456');
  });

  it('clearAuth removes all state', () => {
    const { setTokens, clearAuth } = useAuthStore.getState();
    
    // First set some tokens
    setTokens('access_token_123', 'refresh_token_456');
    
    // Then clear them
    clearAuth();
    
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('login sets isAuthenticated to true on success', async () => {
    const mockResponse = {
      access_token: 'new_access_token',
      refresh_token: 'new_refresh_token',
      user: {
        id: 'user123',
        username: 'testuser',
        displayName: 'Test User',
      },
    };
    
    // Mock fetch for successful login
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });
    
    const { login } = useAuthStore.getState();
    await login('testuser', 'password123');
    
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.accessToken).toBe('new_access_token');
    expect(state.refreshToken).toBe('new_refresh_token');
    expect(state.user).toEqual(mockResponse.user);
    
    // Verify fetch was called with correct parameters
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/login'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'testuser', password: 'password123' }),
      })
    );
  });

  it('login throws error on failure', async () => {
    // Mock fetch for failed login
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
    });
    
    const { login } = useAuthStore.getState();
    
    await expect(login('testuser', 'wrongpassword')).rejects.toThrow('Login failed');
    
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
  });
});
