import { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Radius, Spacing, scale, SCREEN_WIDTH } from '@/constants/theme';

const ALL_INTERESTS = [
  { label: 'Street Art', icon: '🎨' },
  { label: 'History', icon: '🏛️' },
  { label: 'Nature', icon: '🌿' },
  { label: 'Architecture', icon: '🏗️' },
  { label: 'Local Food', icon: '🍜' },
  { label: 'Museums', icon: '🖼️' },
  { label: 'Nightlife', icon: '🌙' },
  { label: 'Shopping', icon: '🛍️' },
  { label: 'Coffee Shops', icon: '☕' },
  { label: 'Live Music', icon: '🎵' },
];

const CHIP_WIDTH = (SCREEN_WIDTH - Spacing.lg * 2 - Spacing.sm) / 2;

export default function OnboardingScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (label: string) => {
    setSelected(prev =>
      prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]
    );
  };

  const handleDone = async () => {
    await AsyncStorage.setItem('user_interests', JSON.stringify(selected));
    router.replace('/(tabs)');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingTop: insets.top + Spacing.lg }]}>
      <Text style={styles.title}>Personalize Your{'\n'}Experience</Text>
      <Text style={styles.subtitle}>Select your interests. This will help us recommend the best spots for you.</Text>

      <View style={styles.grid}>
        {ALL_INTERESTS.map(item => {
          const isActive = selected.includes(item.label);
          return (
            <TouchableOpacity
              key={item.label}
              style={[styles.chip, isActive && styles.chipActive]}
              onPress={() => toggle(item.label)}
            >
              <Text style={styles.chipIcon}>{item.icon}</Text>
              <Text style={[styles.chipLabel, isActive && styles.chipLabelActive]} numberOfLines={1}>
                {item.label}
              </Text>
              {isActive && <Text style={styles.checkmark}>✓</Text>}
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity
        style={[styles.doneBtn, selected.length === 0 && { opacity: 0.4 }]}
        onPress={handleDone}
        disabled={selected.length === 0}
      >
        <Text style={styles.doneBtnText}>Done ({selected.length})</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.primary },
  content: { padding: Spacing.lg },
  title: { fontSize: scale(24), fontWeight: '800', color: Colors.white, marginBottom: scale(6) },
  subtitle: { fontSize: scale(12), color: Colors.tabInactive, lineHeight: scale(18), marginBottom: Spacing.xl },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: {
    width: CHIP_WIDTH,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: Radius.lg,
    paddingVertical: scale(14),
    paddingHorizontal: scale(12),
    flexDirection: 'row',
    alignItems: 'center',
    gap: scale(8),
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  chipActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },
  chipIcon: { fontSize: scale(18) },
  chipLabel: { fontSize: scale(12), fontWeight: '600', color: Colors.white, flex: 1 },
  chipLabelActive: { color: Colors.accent },
  checkmark: { color: Colors.accent, fontSize: scale(14), fontWeight: '700' },
  doneBtn: {
    backgroundColor: Colors.accent, borderRadius: Radius.full,
    paddingVertical: scale(14), alignItems: 'center', marginTop: Spacing.xl,
  },
  doneBtnText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },
});
