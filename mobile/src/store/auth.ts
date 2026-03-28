import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';

interface User {
  id: number;
  email: string;
  full_name: string;
  tenant_id: number;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isHydrated: boolean;
  login: (token: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isHydrated: false,

  login: async (token, user) => {
    await SecureStore.setItemAsync('token', token);
    await SecureStore.setItemAsync('user', JSON.stringify(user));
    set({ token, user });
  },

  logout: async () => {
    await SecureStore.deleteItemAsync('token');
    await SecureStore.deleteItemAsync('user');
    set({ token: null, user: null });
  },

  hydrate: async () => {
    try {
      const token = await SecureStore.getItemAsync('token');
      const userRaw = await SecureStore.getItemAsync('user');
      
      if (token && userRaw) {
        const user = JSON.parse(userRaw);
        set({ token, user, isHydrated: true });
        return;
      }
    } catch (e) {
      console.error('[Auth] Erro ao recuperar sessão offline:', e);
    }
    
    set({ token: null, user: null, isHydrated: true });
  }
}));
