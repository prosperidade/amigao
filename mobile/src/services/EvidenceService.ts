import * as ImagePicker from 'expo-image-picker';
import * as Location from 'expo-location';
import { documentDirectory, getInfoAsync, makeDirectoryAsync, copyAsync, deleteAsync, readAsStringAsync, EncodingType } from 'expo-file-system/legacy';
import { api } from '@/lib/api';
import { getDb } from '@/lib/db';
import { useNetworkStore } from '@/store/network';

export interface CapturedEvidence {
  uri: string;
  latitude: number | null;
  longitude: number | null;
  capturedAt: string;
}

export class EvidenceService {
  /**
   * Solicita permissões de Câmera e Galeria/Localização
   */
  static async requestPermissions() {
    const [cameraStatus, locationStatus] = await Promise.all([
      ImagePicker.requestCameraPermissionsAsync(),
      Location.requestForegroundPermissionsAsync(),
    ]);

    if (cameraStatus.status !== 'granted') {
      throw new Error('Permissão de câmera negada. Por favor, permite nas configurações do celular.');
    }

    return { locationGranted: locationStatus.status === 'granted' };
  }

  /**
   * Abre a câmera nativa e captura foto + GPS simultaneamente
   */
  static async capturePhotoWithLocation(): Promise<CapturedEvidence | null> {
    const { locationGranted } = await this.requestPermissions();

    const [photoResult, locationResult] = await Promise.all([
      ImagePicker.launchCameraAsync({
        mediaTypes: ['images'],
        quality: 0.75, // Compressão para economizar dados
        exif: true,
      }),
      locationGranted
        ? Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High })
        : Promise.resolve(null),
    ]);

    if (photoResult.canceled || !photoResult.assets[0]) {
      return null;
    }

    return {
      uri: photoResult.assets[0].uri,
      latitude: locationResult?.coords.latitude ?? null,
      longitude: locationResult?.coords.longitude ?? null,
      capturedAt: new Date().toISOString(),
    };
  }

  /**
   * Salva a evidência no cache local do sistema de arquivos do dispositivo
   * e registra metadados no SQLite para sincronização futura
   */
  static async saveEvidenceLocally(
    evidence: CapturedEvidence,
    processId: number,
    taskId?: number
  ): Promise<string> {
    // Garante pasta local persistente
    const evidenceDir = documentDirectory + 'evidences/';
    const dirInfo = await getInfoAsync(evidenceDir);
    if (!dirInfo.exists) {
      await makeDirectoryAsync(evidenceDir, { intermediates: true });
    }

    // Copia o arquivo da câmera para pasta gerenciada
    const fileName = `evidence_${processId}_${Date.now()}.jpg`;
    const localPath = evidenceDir + fileName;
    await copyAsync({ from: evidence.uri, to: localPath });

    // Grava metadados no sync_queue para upload posterior
    const db = getDb();
    await db.runAsync(
      `INSERT INTO sync_queue (endpoint, method, payload, status) VALUES (?, ?, ?, ?)`,
      [
        `/processes/${processId}/evidence`,
        'POST',
        JSON.stringify({
          local_path: localPath,
          task_id: taskId ?? null,
          latitude: evidence.latitude,
          longitude: evidence.longitude,
          captured_at: evidence.capturedAt,
          file_name: fileName,
        }),
        'pending_upload', // Status especial para uploads de mídia
      ]
    );

    console.log(`[EvidenceService] Evidence saved locally: ${localPath}`);
    return localPath;
  }

  /**
   * Processa fila de uploads de mídia quando há conexão disponível.
   * Obtém uma Presigned URL do MinIO/S3 e faz upload direto.
   */
  static async uploadPendingEvidences() {
    const isConnected = useNetworkStore.getState().isConnected;
    if (!isConnected) {
      console.log('[EvidenceService] Offline. Uploads adiados.');
      return;
    }

    const db = getDb();
    const pendingUploads: any[] = await db.getAllAsync(
      `SELECT * FROM sync_queue WHERE status = 'pending_upload' ORDER BY created_at ASC LIMIT 5`
    );

    for (const item of pendingUploads) {
      try {
        const meta = JSON.parse(item.payload);

        // 1. Solicita Presigned URL do nosso Backend FastAPI
        const presignRes = await api.post('/documents/upload-url', {
          process_id: parseInt(item.endpoint.split('/')[2]),
          file_name: meta.file_name,
          content_type: 'image/jpeg',
        });

        const { upload_url, storage_key } = presignRes.data;

        // 2. Upload direto para o MinIO/S3 com fetch (sem passar pelo FastAPI)
        const fileContent = await readAsStringAsync(meta.local_path, {
          encoding: EncodingType.Base64,
        });

        // Converte base64 para Blob para upload via fetch
        const blob = await fetch(`data:image/jpeg;base64,${fileContent}`).then(r => r.blob());

        await fetch(upload_url, {
          method: 'PUT',
          body: blob,
          headers: { 'Content-Type': 'image/jpeg' },
        });

        // 3. Confirma upload e salva metadados (GPS, task_id) no Backend
        await api.post('/documents/confirm-upload', {
          storage_key,
          process_id: parseInt(item.endpoint.split('/')[2]),
          task_id: meta.task_id,
          latitude: meta.latitude,
          longitude: meta.longitude,
          captured_at: meta.captured_at,
          original_file_name: meta.file_name,
          source: 'field_app',
        });

        // 4. Marca como sincronizado e apaga arquivo local para liberar espaço
        await db.runAsync(`UPDATE sync_queue SET status = 'synced' WHERE id = ?`, [item.id]);
        await deleteAsync(meta.local_path, { idempotent: true });

        console.log(`[EvidenceService] Evidence ${meta.file_name} uploaded successfully!`);
      } catch (err: any) {
        console.error(`[EvidenceService] Failed to upload evidence (job ${item.id}):`, err.message);
        await db.runAsync(
          `UPDATE sync_queue SET status = 'error', error_message = ? WHERE id = ?`,
          [err.message, item.id]
        );
      }
    }
  }
}
