import { Tabs } from 'expo-router';
import { Briefcase, Settings } from 'lucide-react-native';

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: '#10b981', headerStyle: { backgroundColor: '#f9fafb' } }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Meus Processos',
          tabBarIcon: ({ color }) => <Briefcase color={color} size={24} />,
          headerTitle: 'Visitas em Campo',
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Sistema',
          tabBarIcon: ({ color }) => <Settings color={color} size={24} />,
        }}
      />
    </Tabs>
  );
}
