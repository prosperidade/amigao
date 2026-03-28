import { useEffect, useState } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { useAuthStore } from '@/store/auth';
import { useNetworkStore } from '@/store/network';
import { initDb } from '@/lib/db';
import { View, ActivityIndicator } from 'react-native';

export default function RootLayout() {
  const { isHydrated, hydrate, token } = useAuthStore();
  const initNetworkListener = useNetworkStore(s => s.initNetworkListener);
  const router = useRouter();
  const segments = useSegments();

  const [dbReady, setDbReady] = useState(false);

  // Inicializações globais na partida do app
  useEffect(() => {
    // 1. Escuta mudanças na Internet
    const unsubscribeNetwork = initNetworkListener();
    
    // 2. Tenta recuperar sessão do usuário no SecureStore
    hydrate();

    // 3. Verifica e inicializa o schema do SQLite
    initDb().then(() => setDbReady(true)).catch(console.error);

    return () => unsubscribeNetwork();
  }, []);

  // Guarda de Autenticação Automática
  useEffect(() => {
    if (!isHydrated || !dbReady || !segments) return;

    // Se a rota for vazia e não temos token, vamos ao login
    const isLoginScreen = segments[0] === 'login';
    
    if (!token && !isLoginScreen) {
      // Sem token -> Tela de Login
      router.replace('/login');
    } else if (token && isLoginScreen) {
      // Com token na tela de login -> Cai pra dentro do app
      router.replace('/(tabs)');
    }
  }, [token, isHydrated, dbReady, segments]);

  if (!isHydrated || !dbReady) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#10b981" />
      </View>
    );
  }

  return (
    <Stack>
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="process/[id]" options={{ headerShown: false }} />
      <Stack.Screen name="evidence/[id]" options={{ headerShown: false }} />
    </Stack>
  );
}
