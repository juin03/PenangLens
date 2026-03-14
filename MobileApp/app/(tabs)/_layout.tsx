import { Tabs } from 'expo-router';
import { Text, View, StyleSheet, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, scale } from '@/constants/theme';

function TabIcon({ icon, label, focused }: { icon: string; label: string; focused: boolean }) {
  return (
    <View style={styles.tabItem}>
      <Text style={[styles.tabIcon, focused && styles.tabIconActive]}>{icon}</Text>
      <Text numberOfLines={1} adjustsFontSizeToFit style={[styles.tabLabel, focused && styles.tabLabelActive]}>{label}</Text>
    </View>
  );
}

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: [
          styles.tabBar,
          {
            height: scale(60) + insets.bottom,
            paddingBottom: insets.bottom > 0 ? insets.bottom : scale(6),
          }
        ],
        tabBarShowLabel: false,
      }}
    >
      <Tabs.Screen name="index" options={{ title: 'Discover', tabBarIcon: ({ focused }) => <TabIcon icon="🧭" label="Discover" focused={focused} /> }} />
      <Tabs.Screen name="scan" options={{ title: 'Scan', tabBarIcon: ({ focused }) => <TabIcon icon="📷" label="Scan" focused={focused} /> }} />
      <Tabs.Screen name="itineraries" options={{ title: 'Trips', tabBarIcon: ({ focused }) => <TabIcon icon="🗺️" label="Trips" focused={focused} /> }} />
      <Tabs.Screen name="profile" options={{ title: 'Profile', tabBarIcon: ({ focused }) => <TabIcon icon="👤" label="Profile" focused={focused} /> }} />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: Colors.tabBar,
    borderTopWidth: 0,
    paddingTop: scale(6),
  },
  tabItem: { alignItems: 'center', gap: 2 },
  tabIcon: { fontSize: scale(20) },
  tabIconActive: { fontSize: scale(22) },
  tabLabel: { fontSize: scale(10), color: Colors.tabInactive, fontWeight: '500' },
  tabLabelActive: { color: Colors.tabActive, fontWeight: '700' },
});
