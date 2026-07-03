import { Tabs } from 'expo-router';
import { Text, View, StyleSheet, TouchableOpacity } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors, scale } from '@/constants/theme';

function TabIcon({
  iconName,
  label,
  color,
  focused,
}: {
  iconName: keyof typeof Ionicons.glyphMap;
  label: string;
  color: string;
  focused: boolean;
}) {
  return (
    <View style={styles.tabItem}>
      <Ionicons name={iconName} size={scale(24)} color={color} style={{ opacity: focused ? 1 : 0.7 }} />
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
            <TabIcon iconName={focused ? "compass" : "compass-outline"} label="Discover" color={color} focused={focused} />
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
            <TabIcon iconName={focused ? "scan" : "scan-outline"} label="Scan" color={color} focused={focused} />
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
            <TabIcon iconName={focused ? "map" : "map-outline"} label="Trips" color={color} focused={focused} />
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
            <TabIcon iconName={focused ? "person" : "person-outline"} label="Profile" color={color} focused={focused} />
          ),
        }}
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
  tabLabel: {
    fontSize: scale(11),
    fontWeight: '500',
  },
});