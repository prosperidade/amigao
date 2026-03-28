import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// No emulador Android puro, localhost = 10.0.2.2.
// Para acesso via Expo Go no celular físico (LAN), usamos o IP da máquina do servidor Backend:
const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://192.168.1.42:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
  (error) => {
    return Promise.reject(error);
  }
);
