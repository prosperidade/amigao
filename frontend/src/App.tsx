import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Login from './pages/Auth/Login';
import PrivateLayout from './layouts/PrivateLayout';
import Dashboard from './pages/Dashboard';
import ClientsPage from './pages/Clients';
import ProcessesPage from './pages/Processes';
import PropertiesPage from './pages/Properties';

// Query Client para gerenciar cache das requisições
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          
          {/* Rotas Públicas */}
          <Route path="/login" element={<Login />} />
          
          {/* Rotas Privadas (Placeholder) */}
          <Route element={<PrivateLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            {/* Telas que serão implementadas a seguir */}
            <Route path="/processes" element={<ProcessesPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/properties" element={<PropertiesPage />} />
          </Route>
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
