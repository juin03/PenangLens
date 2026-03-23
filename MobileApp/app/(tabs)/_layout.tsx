import { Tabs } from 'expo-router';
import { Text, View, StyleSheet, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, scale } from '@/constants/theme';

function TabIcon({
  icon,
  label,
  color,
  focused,
}: {
  icon: string;
  label: string;
  color: string;
  focused: boolean;
}) {
  return (
    <View style={styles.tabItem}>
      <Text style={[styles.tabIcon, { opacity: focused ? 1 : 0.7 }]}>
        {icon}
      </Text>
      <Text
        numberOfLines={1}
        adjustsFontSizeToFit
        style={[styles.tabLabel, { color, fontWeight: focused ? '700' : '500' }]}
      >
        {label}
      </Text>
    </View>
  );
}

export default function TabLayout() {
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: {
          backgroundColor: Colors.tabBar,
          borderTopWidth: 0,
          paddingTop: scale(6),
          height: scale(60) + (insets.bottom > 0 ? insets.bottom : scale(6)),
          paddingBottom: insets.bottom > 0 ? insets.bottom : scale(6),
          flexDirection: 'row',
        },
        tabBarActiveTintColor: Colors.tabActive,
        tabBarInactiveTintColor: Colors.tabInactive,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Discover',
          tabBarButton: (props) => (
            <TouchableOpacity {...props} style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} />
          ),
          tabBarIcon: ({ color, focused }) => (
            <TabIcon icon="🧭" label="Discover" color={color} focused={focused} />
          ),
        }}
      />

      <Tabs.Screen
        name="scan"
        options={{
          title: 'Scan',
          tabBarButton: (props) => (
            <TouchableOpacity {...props} style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} />
          ),
          tabBarIcon: ({ color, focused }) => (
            <TabIcon icon="📷" label="Scan" color={color} focused={focused} />
          ),
        }}
      />

      <Tabs.Screen
        name="itineraries"
        options={{
          title: 'Trips',
          tabBarButton: (props) => (
            <TouchableOpacity {...props} style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} />
          ),
          tabBarIcon: ({ color, focused }) => (
            <TabIcon icon="🗺️" label="Trips" color={color} focused={focused} />
          ),
        }}
      />

      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarButton: (props) => (
            <TouchableOpacity {...props} style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }} />
          ),
          tabBarIcon: ({ color, focused }) => (
            <TabIcon icon="👤" label="Profile" color={color} focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile_old"
        options={{ href: null }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
    width: '100%',
  },
  tabIcon: {
    fontSize: scale(20),
  },
  tabLabel: {
    fontSize: scale(10),
    fontWeight: '500',
  },
});