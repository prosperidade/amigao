import { create } from 'zustand';
import NetInfo from '@react-native-community/netinfo';

interface NetworkState {
  isConnected: boolean | null;
  isInternetReachable: boolean | null;
  type: string;
  initNetworkListener: () => () => void;
}

export const useNetworkStore = create<NetworkState>((set) => ({
  isConnected: true,
  isInternetReachable: true,
  type: 'unknown',

  initNetworkListener: () => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      set({
        isConnected: state.isConnected,
        isInternetReachable: state.isInternetReachable,
        type: state.type,
      });
      console.log(`[Network] Status changed: Connected=${state.isConnected}, Type=${state.type}`);
    });

    return unsubscribe;
  }
}));
