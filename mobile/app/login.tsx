import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useAuthStore } from '@/store/auth';
import { api } from '@/lib/api';
import { SyncService } from '@/services/SyncService';
import { Leaf } from 'lucide-react-native';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const authLogin = useAuthStore(s => s.login);

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError('');
      
      const payload = new URLSearchParams();
      payload.append('username', email);
      payload.append('password', password);

      // Usamos URLSearchParams pois a API OAuth padrão do FastAPI requer application/x-www-form-urlencoded !! IMPORTANTE
      const res = await api.post('/auth/login', payload.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      
      const { access_token } = res.data;
      
      // Busca dados do User
      const userRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${access_token}` }
      });
      
      await authLogin(access_token, userRes.data);
      
      // Dispara pull agressivo logo após o login no Wi-Fi
      await SyncService.pullActiveProcesses();

    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(axiosErr.response?.data?.detail || 'Erro ao conectar. Verifique sua conexão(ou IP).');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: '#f9fafb', padding: 24, justifyContent: 'center' }}>
      <View style={{ alignItems: 'center', marginBottom: 40 }}>
        <View style={{ backgroundColor: '#ecfdf5', padding: 16, borderRadius: 20, marginBottom: 16 }}>
          <Leaf color="#10b981" size={40} />
        </View>
        <Text style={{ fontSize: 28, fontWeight: 'bold', color: '#111827' }}>Amigão</Text>
        <Text style={{ fontSize: 16, color: '#6b7280', marginTop: 4 }}>Para Analistas de Campo</Text>
      </View>

      <View style={{ gap: 16 }}>
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="E-mail corporativo"
          autoCapitalize="none"
          keyboardType="email-address"
          style={{ backgroundColor: 'white', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb', fontSize: 16 }}
        />
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder="Senha"
          secureTextEntry
          style={{ backgroundColor: 'white', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb', fontSize: 16 }}
        />
        
        {error ? <Text style={{ color: '#ef4444', textAlign: 'center', fontWeight: '500' }}>{error}</Text> : null}

        <TouchableOpacity
          onPress={handleLogin}
          disabled={loading || !email.trim() || !password.trim()}
          style={{ backgroundColor: (!email.trim() || !password.trim()) ? '#9ca3af' : '#10b981', padding: 16, borderRadius: 12, alignItems: 'center', marginTop: 8, opacity: loading || !email.trim() || !password.trim() ? 0.7 : 1 }}
        >
          {loading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text style={{ color: 'white', fontWeight: 'bold', fontSize: 16 }}>Entrar e Sincronizar</Text>
          )}
        </TouchableOpacity>
      </View>

      <Text style={{ textAlign: 'center', color: '#9ca3af', marginTop: 40, fontSize: 12 }}>
        Certifique-se de realizar o login enquanto conectado à rede da empresa para baixar os processos antes de ir ao campo.
      </Text>
    </View>
  );
}
