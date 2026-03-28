import { useState } from 'react';
import { View, Text, TouchableOpacity, Image, ScrollView, Alert } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { EvidenceService, CapturedEvidence } from '@/services/EvidenceService';
import { useNetworkStore } from '@/store/network';
import { Camera, MapPin, Upload, Wifi, WifiOff, CheckCircle2 } from 'lucide-react-native';

export default function EvidenceCaptureScreen() {
  const { processId } = useLocalSearchParams();
  const isConnected = useNetworkStore(s => s.isConnected);
  const [captured, setCaptured] = useState<CapturedEvidence | null>(null);
  const [uploading, setUploading] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleCapture = async () => {
    try {
      const evidence = await EvidenceService.capturePhotoWithLocation();
      if (evidence) {
        setCaptured(evidence);
        setSaved(false);
      }
    } catch (err: any) {
      Alert.alert('Erro de Permissão', err.message);
    }
  };

  const handleSaveOrUpload = async () => {
    if (!captured || !processId) return;
    setUploading(true);
    try {
      // Salva localmente e registra na fila (independente de ter internet)
      await EvidenceService.saveEvidenceLocally(captured, Number(processId));

      // Se tiver conexão, tenta subir imediatamente
      if (isConnected) {
        await EvidenceService.uploadPendingEvidences();
      }
      setSaved(true);
    } catch (err: any) {
      Alert.alert('Erro', 'Não foi possível salvar a evidência: ' + err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: '#f9fafb' }} contentContainerStyle={{ padding: 24 }}>
      <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#111827', marginBottom: 4 }}>
        Captura de Evidência
      </Text>
      <Text style={{ color: '#6b7280', marginBottom: 24 }}>
        Processo #{processId}
      </Text>

      {/* Status de rede */}
      <View style={{
        flexDirection: 'row', alignItems: 'center', padding: 12, borderRadius: 10,
        backgroundColor: isConnected ? '#ecfdf5' : '#fef2f2', marginBottom: 24,
      }}>
        {isConnected ? <Wifi color="#10b981" size={18} /> : <WifiOff color="#ef4444" size={18} />}
        <Text style={{ marginLeft: 8, fontSize: 13, fontWeight: '600', color: isConnected ? '#065f46' : '#991b1b' }}>
          {isConnected ? 'Online — Upload imediato após captura' : 'Offline — Foto salva e enviada quando voltar o sinal'}
        </Text>
      </View>

      {/* Preview da foto */}
      {captured ? (
        <View style={{ marginBottom: 24 }}>
          <Image source={{ uri: captured.uri }} style={{ width: '100%', height: 300, borderRadius: 16, marginBottom: 16 }} />

          {/* Metadados GPS */}
          <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: 'white', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#e5e7eb' }}>
            <MapPin color="#10b981" size={18} />
            <Text style={{ marginLeft: 8, color: '#374151', fontSize: 13 }}>
              {captured.latitude != null
                ? `GPS: ${captured.latitude.toFixed(6)}, ${captured.longitude?.toFixed(6)}`
                : 'Localização não disponível'}
            </Text>
          </View>
        </View>
      ) : (
        <View style={{ height: 240, borderRadius: 16, backgroundColor: '#e5e7eb', justifyContent: 'center', alignItems: 'center', marginBottom: 24 }}>
          <Camera color="#9ca3af" size={48} />
          <Text style={{ color: '#9ca3af', marginTop: 12, fontSize: 14 }}>Nenhuma foto capturada</Text>
        </View>
      )}

      {/* Botão principal */}
      {!saved ? (
        <>
          <TouchableOpacity
            onPress={handleCapture}
            style={{ backgroundColor: '#111827', padding: 18, borderRadius: 14, alignItems: 'center', marginBottom: 12 }}
          >
            <Camera color="white" size={22} />
            <Text style={{ color: 'white', fontWeight: 'bold', marginTop: 6 }}>Abrir Câmera</Text>
          </TouchableOpacity>

          {captured && (
            <TouchableOpacity
              onPress={handleSaveOrUpload}
              disabled={uploading}
              style={{ backgroundColor: '#10b981', padding: 18, borderRadius: 14, alignItems: 'center' }}
            >
              <Upload color="white" size={22} />
              <Text style={{ color: 'white', fontWeight: 'bold', marginTop: 6 }}>
                {uploading ? 'Salvando...' : isConnected ? 'Salvar e Enviar Agora' : 'Salvar Offline'}
              </Text>
            </TouchableOpacity>
          )}
        </>
      ) : (
        <View style={{ alignItems: 'center', padding: 24 }}>
          <CheckCircle2 color="#10b981" size={48} />
          <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#065f46', marginTop: 12 }}>Evidência Registrada!</Text>
          <Text style={{ color: '#6b7280', marginTop: 4, textAlign: 'center' }}>
            {isConnected ? 'A foto foi enviada ao servidor com as coordenadas GPS.' : 'A foto está salva no dispositivo e será enviada automaticamente.'}
          </Text>
          <TouchableOpacity onPress={() => { setCaptured(null); setSaved(false); }} style={{ marginTop: 24 }}>
            <Text style={{ color: '#10b981', fontWeight: '600' }}>Capturar Nova Foto</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}
