import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="index" />
        <Stack.Screen name="login" />
        <Stack.Screen name="signup" />
        <Stack.Screen name="forgot-password" />
        <Stack.Screen name="onboarding" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="plan"
          options={{ headerShown: true, title: 'Plan Your Trip', headerTintColor: '#1B3A4B' }}
        />
        <Stack.Screen
          name="itinerary"
          options={{ headerShown: true, title: 'Your Itinerary', headerTintColor: '#1B3A4B' }}
        />
        <Stack.Screen name="landmark/result" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="light" />
    </SafeAreaProvider>
  );
}
