import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Radius, Spacing, scale, SCREEN_WIDTH } from '@/constants/theme';
import { updateProfile } from '@/api/client';

const LEGACY_TO_CANONICAL: Record<string, string> = {
  'street art': 'Art',
  'history': 'Historical',
  'nature': 'Nature',
  'architecture': 'Architecture',
  'local food': 'Food',
  'museums': 'Art',
  'nightlife': 'Shopping',
  'shopping': 'Shopping',
  'coffee shops': 'Food',
  'live music': 'Art',
  'heritage': 'Heritage',
  'food': 'Food',
  'art': 'Art',
  'religious': 'Religious',
  'historical': 'Historical',
};

const ALL_INTERESTS = [
  { label: 'Heritage', icon: '🏛️', description: 'Historic districts, traditions, and cultural identity.' },
  { label: 'Food', icon: '🍜', description: 'Hawker culture, local dishes, and authentic flavors.' },
  { label: 'Nature', icon: '🌿', description: 'Parks, hills, gardens, and scenic views.' },
  { label: 'Art', icon: '🎨', description: 'Street art, galleries, exhibits, and creative spaces.' },
  { label: 'Religious', icon: '🛕', description: 'Temples, mosques, churches, and spiritual landmarks.' },
  { label: 'Shopping', icon: '🛍️', description: 'Malls, markets, souvenirs, and local finds.' },
  { label: 'Historical', icon: '📜', description: 'Monuments, colonial stories, and key past events.' },
  { label: 'Architecture', icon: '🏗️', description: 'Beautiful building styles and landmark design.' },
];

const CHIP_WIDTH = (SCREEN_WIDTH - Spacing.lg * 2 - Spacing.sm) / 2;

export default function OnboardingScreen() {
  const router = useRouter();
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const insets = useSafeAreaInsets();
  const [selected, setSelected] = useState<string[]>([]);
  const isEditMode = mode === 'edit';

  const normalizeInterests = (raw: string[]): string[] => {
    const mapped = raw
      .map(value => LEGACY_TO_CANONICAL[String(value).trim().toLowerCase()] || value)
      .filter(Boolean);
    const deduped = Array.from(new Set(mapped));
    const allowed = new Set(ALL_INTERESTS.map(i => i.label));
    return deduped.filter(v => allowed.has(v));
  };

  useEffect(() => {
    (async () => {
      const interestsRaw = await AsyncStorage.getItem('user_interests');
      if (interestsRaw) {
        const parsed = JSON.parse(interestsRaw);
        if (Array.isArray(parsed)) {
          const normalized = normalizeInterests(parsed);
          setSelected(normalized);
          await AsyncStorage.setItem('user_interests', JSON.stringify(normalized));
        }
      }
    })();
  }, []);

  const toggle = (label: string) => {
    setSelected(prev =>
      prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]
    );
  };

  const handleDone = async () => {
    await AsyncStorage.setItem('user_interests', JSON.stringify(selected));
    try {
      await updateProfile({ interests: selected });
    } catch {
    }
    if (isEditMode) {
      router.back();
      return;
    }
    router.replace('/(tabs)');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingTop: insets.top + Spacing.lg }]}>
      <Text style={styles.title}>{isEditMode ? 'Update Your Interests' : 'Personalize Your\nExperience'}</Text>
      <Text style={styles.subtitle}>Choose what you enjoy most so we can rank spots that fit you better.</Text>
      <Text style={styles.counter}>Selected: {selected.length}</Text>

      <View style={styles.grid}>
        {ALL_INTERESTS.map(item => {
          const isActive = selected.includes(item.label);
          return (
            <TouchableOpacity
              key={item.label}
              style={[styles.card, isActive && styles.cardActive]}
              onPress={() => toggle(item.label)}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.cardIcon}>{item.icon}</Text>
                <Text style={[styles.cardLabel, isActive && styles.cardLabelActive]} numberOfLines={1}>
                  {item.label}
                </Text>
                {isActive && <Text style={styles.checkmark}>✓</Text>}
              </View>
              <Text style={[styles.cardDescription, isActive && styles.cardDescriptionActive]} numberOfLines={3}>
                {item.description}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity
        style={[styles.doneBtn, selected.length === 0 && { opacity: 0.4 }]}
        onPress={handleDone}
        disabled={selected.length === 0}
      >
        <Text style={styles.doneBtnText}>{isEditMode ? `Save Interests (${selected.length})` : `Done (${selected.length})`}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.primary },
  content: { padding: Spacing.lg },
  title: { fontSize: scale(24), fontWeight: '800', color: Colors.white, marginBottom: scale(6) },
  subtitle: { fontSize: scale(12), color: Colors.tabInactive, lineHeight: scale(18), marginBottom: Spacing.sm },
  counter: { fontSize: scale(12), color: Colors.accent, fontWeight: '700', marginBottom: Spacing.lg },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  card: {
    width: CHIP_WIDTH,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: Radius.lg,
    minHeight: scale(118),
    paddingVertical: scale(12),
    paddingHorizontal: scale(12),
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  cardActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: scale(8) },
  cardIcon: { fontSize: scale(18), marginRight: scale(8) },
  cardLabel: { fontSize: scale(12), fontWeight: '700', color: Colors.white, flex: 1 },
  cardLabelActive: { color: Colors.accent },
  cardDescription: { fontSize: scale(10.5), color: Colors.tabInactive, lineHeight: scale(15) },
  cardDescriptionActive: { color: Colors.white },
  checkmark: { color: Colors.accent, fontSize: scale(14), fontWeight: '700' },
  doneBtn: {
    backgroundColor: Colors.accent, borderRadius: Radius.full,
    paddingVertical: scale(14), alignItems: 'center', marginTop: Spacing.xl,
  },
  doneBtnText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },
});
