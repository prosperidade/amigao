import { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { getDb } from '@/lib/db';
import { SyncService } from '@/services/SyncService';
import { CheckCircle2, Circle, ArrowLeft, ArrowUpCircle, Camera } from 'lucide-react-native';

export default function ProcessDetailsScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  
  const [processInfo, setProcessInfo] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);

  const loadProcessAndTasks = async () => {
    try {
      const db = getDb();
      const pData = await db.getAllAsync('SELECT * FROM processes WHERE id = ?', [Number(id)]);
      if (pData.length > 0) setProcessInfo(pData[0]);

      const tData = await db.getAllAsync('SELECT * FROM tasks WHERE process_id = ? ORDER BY id ASC', [Number(id)]);
      setTasks(tData);
    } catch (err) {
      console.error('[ProcessDetails] Erro ao carregar SQLite:', err);
    }
  };

  useEffect(() => {
    loadProcessAndTasks();
  }, [id]);

  const handleToggleTask = async (task: any) => {
    const newStatus = task.status === 'done' ? 'todo' : 'done';
    
    try {
      const db = getDb();
      // 1. Atualização Otimista no Aparelho (Sem depender da internet)
      await db.runAsync(`UPDATE tasks SET status = ? WHERE id = ?`, [newStatus, task.id]);
      
      // 2. Coloca o patch na SyncQueue
      await SyncService.enqueueMutation(`/tasks/${task.id}/status`, 'PATCH', {
        status: newStatus
      });

      // Recarrega a view local
      loadProcessAndTasks();

    } catch (e) {
      console.error('[ProcessDetails] Falha ao marcar tarefa offline:', e);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: '#f9fafb' }}>
      <View style={{ backgroundColor: 'white', padding: 16, paddingTop: 60, paddingBottom: 24, borderBottomWidth: 1, borderColor: '#e5e7eb' }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <TouchableOpacity onPress={() => router.back()} style={{ flexDirection: 'row', alignItems: 'center' }}>
            <ArrowLeft size={20} color="#6b7280" />
            <Text style={{ marginLeft: 8, color: '#6b7280', fontSize: 16, fontWeight: '500' }}>Voltar</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push(`/evidence/${id}`)}
            style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#ecfdf5', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 }}
          >
            <Camera size={18} color="#10b981" />
            <Text style={{ marginLeft: 6, color: '#10b981', fontWeight: '600', fontSize: 14 }}>Evidência</Text>
          </TouchableOpacity>
        </View>
        
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <View style={{ backgroundColor: '#ecfdf5', padding: 12, borderRadius: 12 }}>
            <ArrowUpCircle color="#10b981" size={28} />
          </View>
          <View style={{ marginLeft: 16, flex: 1 }}>
            <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#111827' }}>
              {processInfo?.name || 'Carregando...'}
            </Text>
            <Text style={{ color: '#6b7280', marginTop: 4 }}>
              Status Atual: {processInfo?.status?.toUpperCase()}
            </Text>
          </View>
        </View>
      </View>

      <View style={{ padding: 16, flex: 1 }}>
        <Text style={{ fontSize: 18, fontWeight: '600', color: '#374151', marginBottom: 16 }}>Checklist de Operação em Campo</Text>
        
        <FlatList
          data={tasks}
          keyExtractor={(t) => t.id.toString()}
          ListEmptyComponent={
            <Text style={{ color: '#9ca3af', textAlign: 'center', marginTop: 32 }}>Este processo não possui checklists registrados.</Text>
          }
          renderItem={({ item }) => {
            const isDone = item.status === 'done';
            return (
              <TouchableOpacity 
                onPress={() => handleToggleTask(item)}
                style={{ 
                  flexDirection: 'row', 
                  alignItems: 'center', 
                  backgroundColor: 'white', 
                  padding: 16, 
                  borderRadius: 12, 
                  borderWidth: 1, 
                  borderColor: isDone ? '#10b981' : '#e5e7eb',
                  marginBottom: 12,
                  opacity: isDone ? 0.7 : 1
                }}
              >
                {isDone ? (
                  <CheckCircle2 color="#10b981" size={24} />
                ) : (
                  <Circle color="#d1d5db" size={24} />
                )}
                <View style={{ marginLeft: 16, flex: 1 }}>
                  <Text style={{ fontSize: 16, fontWeight: '500', color: isDone ? '#9ca3af' : '#111827', textDecorationLine: isDone ? 'line-through' : 'none' }}>
                    {item.title}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          }}
        />
      </View>
    </View>
  );
}
