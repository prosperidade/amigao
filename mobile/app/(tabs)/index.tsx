import { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, RefreshControl } from 'react-native';
import { useRouter } from 'expo-router';
import { getDb } from '@/lib/db';
import { useNetworkStore } from '@/store/network';
import { SyncService } from '@/services/SyncService';
import { Wifi, WifiOff, MapPin, ChevronRight, Activity } from 'lucide-react-native';

export default function ProcessListScreen() {
  const router = useRouter();
  const isConnected = useNetworkStore(s => s.isConnected);
  const [processes, setProcesses] = useState<any[]>([]);
  const [queueCount, setQueueCount] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const loadLocalData = async () => {
    try {
      const db = getDb();
      // Leitura 100% OFF-LINE (Super Rápida em Campo)
      const data = await db.getAllAsync('SELECT * FROM processes ORDER BY due_date ASC');
      setProcesses(data);

      const q = await db.getAllAsync(`SELECT count(id) as total FROM sync_queue WHERE status = 'pending'`);
      setQueueCount((q[0] as any).total || 0);
    } catch (e) {
      console.error('[ProcessList] Erro ao carregar processos SQLite', e);
    }
  };

  useEffect(() => {
    loadLocalData();
  }, [isConnected]); // Recarregar QTD da Fila quando volta a internet

  const onRefresh = async () => {
    setRefreshing(true);
    if (isConnected) {
      // Se tiver internet, podemos tentar forçar um Pull do Servidor pro SQLite
      await SyncService.pullActiveProcesses();
    }
    await loadLocalData();
    setRefreshing(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: '#f9fafb' }}>
      {/* Banner de Status de Rede */}
      <View style={{ 
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', padding: 8,
        backgroundColor: isConnected ? '#ecfdf5' : '#fef2f2',
      }}>
        {isConnected ? <Wifi color="#10b981" size={16} /> : <WifiOff color="#ef4444" size={16} />}
        <Text style={{ marginLeft: 8, fontSize: 13, fontWeight: '600', color: isConnected ? '#065f46' : '#991b1b' }}>
          {isConnected ? 'Online. Sincronizado com Amigão SaaS' : 'Offline. Operando pelo Banco Local (Sem Sinal)'}
        </Text>
      </View>

      {/* Sync Queue Monitor */}
      {queueCount > 0 && (
        <View style={{ backgroundColor: '#fffbeb', padding: 12, borderBottomWidth: 1, borderColor: '#fef3c7', flexDirection: 'row', alignItems: 'center' }}>
          <Activity color="#d97706" size={20} />
          <Text style={{ marginLeft: 8, fontSize: 13, color: '#92400e', flex: 1 }}>
            Você possui <Text style={{fontWeight: 'bold'}}>{queueCount} atualizações em campo</Text> na fila aguardando conexão.
          </Text>
          {isConnected && (
            <TouchableOpacity onPress={() => SyncService.pushPendingMutations().then(() => loadLocalData())} style={{ backgroundColor: '#f59e0b', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6 }}>
              <Text style={{ color: 'white', fontSize: 12, fontWeight: 'bold' }}>Forçar Envio</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Listagem do SQLite */}
      <FlatList
        data={processes}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={{ padding: 16, gap: 12 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={
          <View style={{ padding: 32, alignItems: 'center' }}>
            <Text style={{ color: '#6b7280', textAlign: 'center' }}>
              Nenhum processo salvo na memória do dispositivo. Conecte-se na sede da empresa para baixar suas visitas!
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <TouchableOpacity 
            onPress={() => router.push(`/process/${item.id}`)}
            style={{ backgroundColor: 'white', padding: 16, borderRadius: 12, borderWidth: 1, borderColor: '#e5e7eb', elevation: 1 }}
          >
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <View style={{ flex: 1, paddingRight: 16 }}>
                <Text style={{ fontWeight: 'bold', fontSize: 16, color: '#111827', marginBottom: 4 }}>
                  {item.name}
                </Text>
                
                <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
                  <MapPin size={14} color="#6b7280" />
                  <Text style={{ color: '#6b7280', fontSize: 13, marginLeft: 4 }}>
                    Imóvel #{item.property_id || 'Não atrelado'}
                  </Text>
                </View>
              </View>
              
              <View style={{ alignItems: 'flex-end', justifyContent: 'center', height: '100%' }}>
                <View style={{ backgroundColor: '#f3f4f6', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, marginBottom: 8 }}>
                  <Text style={{ fontSize: 11, fontWeight: 'bold', textTransform: 'uppercase', color: '#4b5563' }}>
                    {item.status}
                  </Text>
                </View>
                <ChevronRight color="#d1d5db" size={24} />
              </View>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}
