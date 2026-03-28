import { View, Text, TouchableOpacity } from 'react-native';
import { useAuthStore } from '@/store/auth';
import { LogOut } from 'lucide-react-native';

export default function SettingsScreen() {
  const logout = useAuthStore(s => s.logout);
  const user = useAuthStore(s => s.user);

  return (
    <View style={{ flex: 1, backgroundColor: '#f9fafb', padding: 24 }}>
      <View style={{ backgroundColor: 'white', padding: 24, borderRadius: 16, alignItems: 'center', marginBottom: 40, borderWidth: 1, borderColor: '#e5e7eb' }}>
        <View style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: '#10b981', alignItems: 'center', justifyContent: 'center', marginBottom: 16 }}>
          <Text style={{ fontSize: 24, fontWeight: 'bold', color: 'white' }}>
            {user?.full_name?.charAt(0).toUpperCase()}
          </Text>
        </View>
        <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#111827' }}>{user?.full_name}</Text>
        <Text style={{ fontSize: 14, color: '#6b7280', marginTop: 4 }}>{user?.email}</Text>
      </View>

      <TouchableOpacity 
        onPress={logout}
        style={{ backgroundColor: '#fee2e2', padding: 16, borderRadius: 12, flexDirection: 'row', justifyContent: 'center', alignItems: 'center' }}
      >
        <LogOut color="#ef4444" size={20} />
        <Text style={{ color: '#ef4444', fontWeight: 'bold', fontSize: 16, marginLeft: 8 }}>Sair da Conta (Logout)</Text>
      </TouchableOpacity>
      <Text style={{ textAlign: 'center', color: '#9ca3af', marginTop: 12, fontSize: 12 }}>
        Fazer logout apagará suas credenciais do cofre seguro.
      </Text>
    </View>
  );
}
