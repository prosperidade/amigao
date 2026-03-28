import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  user: { email?: string | null } | null;
  hydrated: boolean;
  login: (token: string, user: { email?: string | null } | null) => void;
  logout: () => void;
  markHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      hydrated: false,
      login: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
      markHydrated: () => set({ hydrated: true }),
    }),
    {
      name: 'client-portal-auth',
      onRehydrateStorage: () => (state) => {
        state?.markHydrated();
      },
    }
  )
);
