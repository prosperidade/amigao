/**
 * Tipagem das variáveis de ambiente expostas pelo Expo (prefixo EXPO_PUBLIC_).
 * Estende a declaração global de ProcessEnv sem modificar o expo-env.d.ts gerado.
 */
declare namespace NodeJS {
  interface ProcessEnv {
    /** URL base da API backend, ex: http://localhost:8000/api/v1 */
    EXPO_PUBLIC_API_URL?: string;
  }
}
