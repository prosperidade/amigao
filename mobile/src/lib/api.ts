import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/**
 * Resolve a URL base da API:
 * 1. Variável de ambiente (definida em .env.local)
 * 2. Fallback por plataforma (emulador Android usa 10.0.2.2)
 */
function resolveApiUrl(): string {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  // Android emulator mapeia localhost para 10.0.2.2
  const host = Platform.OS === 'android' ? '10.0.2.2' : 'localhost';
  return `http://${host}:8000/api/v1`;
}

const API_URL = resolveApiUrl();

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// --- Request interceptor: injeta JWT ---
api.interceptors.request.use(
  async (config) => {
    try {
      const token = await SecureStore.getItemAsync('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('[API] Erro ao recuperar token', error);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// --- Response interceptor: logout automático em 401 ---
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.warn('[API] 401 Unauthorized — limpando sessão e forçando logout.');
      try {
        await SecureStore.deleteItemAsync('token');
        await SecureStore.deleteItemAsync('user');
      } catch (cleanupError) {
        console.error('[API] Erro ao limpar SecureStore no logout forçado', cleanupError);
      }
      // Emite evento global para que telas/navigation reajam ao logout
      api.defaults.headers.common['Authorization'] = '';
    }
    return Promise.reject(error);
  },
);
