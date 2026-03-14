import { useEffect } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Colors, scale } from '@/constants/theme';

export default function SplashScreen() {
  const router = useRouter();
  const fadeAnim = new Animated.Value(0);
  const scaleAnim = new Animated.Value(0.8);

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
      Animated.spring(scaleAnim, { toValue: 1, tension: 50, friction: 7, useNativeDriver: true }),
    ]).start();

    const timer = setTimeout(async () => {
      const token = await AsyncStorage.getItem('auth_token');
      if (token) {
        router.replace('/(tabs)');
      } else {
        router.replace('/login');
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.logoWrap, { opacity: fadeAnim, transform: [{ scale: scaleAnim }] }]}>
        <Text style={styles.logoIcon}>🏛️</Text>
        <Text style={styles.title}>
          PENANG<Text style={styles.accent}>LENS</Text>
        </Text>
        <Text style={styles.tagline}>Explore • Discover • Experience</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.primary, justifyContent: 'center', alignItems: 'center' },
  logoWrap: { alignItems: 'center' },
  logoIcon: { fontSize: scale(56), marginBottom: scale(12) },
  title: { fontSize: scale(32), fontWeight: '900', color: Colors.white, letterSpacing: 2 },
  accent: { color: Colors.accent },
  tagline: { fontSize: scale(12), color: Colors.tabInactive, marginTop: scale(6), letterSpacing: 1 },
});
