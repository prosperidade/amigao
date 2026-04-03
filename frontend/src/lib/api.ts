import axios from 'axios';
import { useAuthStore } from '@/store/auth';

const API_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para injetar o Token JWT e o Tenant ID em todas as requisições
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    const user = useAuthStore.getState().user;
    
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    // A API FastAPI espera o header X-Tenant-Id obrigatório para isolamento
    if (user?.tenant_id) {
      config.headers['X-Tenant-Id'] = user.tenant_id.toString();
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor para capturar 401/403 e limpar o state logando out automaticamente
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
