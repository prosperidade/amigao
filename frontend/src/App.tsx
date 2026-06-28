import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import Login from './pages/Auth/Login';
import PrivateLayout from './layouts/PrivateLayout';
import Dashboard from './pages/Dashboard';
import ClientsPage from './pages/Clients';
import ClientHub from './pages/Clients/ClientHub';
import ProcessesPage from './pages/Processes';
import ProcessDetail from './pages/Processes/ProcessDetail';
import PropertiesPage from './pages/Properties';
import PropertyHub from './pages/Properties/PropertyHub';
import IntakeWizard from './pages/Intake/IntakeWizard';
import ProposalList from './pages/Proposals/ProposalList';
import ProposalEditor from './pages/Proposals/ProposalEditor';
import ContractEditor from './pages/Contracts/ContractEditor';
import AgentsPage from './pages/AI/AgentsPage';
import Settings from './pages/Settings';

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
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Toaster position="top-right" />
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
            <Route path="/processes/:id" element={<ProcessDetail />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/clients/:id" element={<ClientHub />} />
            <Route path="/properties" element={<PropertiesPage />} />
            <Route path="/properties/:id" element={<PropertyHub />} />
            <Route path="/intake" element={<IntakeWizard />} />
            <Route path="/proposals" element={<ProposalList />} />
            <Route path="/proposals/new" element={<ProposalEditor />} />
            <Route path="/proposals/:id" element={<ProposalEditor />} />
            <Route path="/contracts/:id" element={<ContractEditor />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
