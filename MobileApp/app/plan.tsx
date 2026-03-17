import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { generateItinerary, saveItinerary } from '@/api/client';

const INTEREST_TAGS = ['Food', 'Art', 'Nature', 'Heritage', 'Nightlife', 'Shopping', 'Culture', 'Beach'];

export default function PlanTripScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [description, setDescription] = useState('');
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('17:00');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [travelMode, setTravelMode] = useState<'walking' | 'driving' | 'transit'>('walking');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleInterest = (tag: string) =>
    setSelectedInterests(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);

  const handleGenerate = async () => {
    if (!description.trim()) { setError('Please describe what you want to do.'); return; }
    setLoading(true); setError('');
    try {
      const result = await generateItinerary({
        description, interests: selectedInterests,
        start_time: startTime, end_time: endTime,
        start_location: 'George Town, Penang', travel_mode: travelMode,
        ...(startDate ? { start_date: startDate } : {}),
        ...(endDate ? { end_date: endDate } : {}),
      });

      let itineraryId: string | undefined;
      try {
        const structured = result?.structured_itinerary;
        const serializedStructured = structured ? JSON.stringify(structured) : undefined;

        const saved = await saveItinerary({
          name: structured?.summary || 'My Penang Trip',
          originalPrompt: description,
          generatedNarrative: serializedStructured || result?.response || structured?.summary,
          totalDuration: structured?.total_duration_min,
        });
        itineraryId = saved?.itinerary?.id;
      } catch {
        itineraryId = undefined;
      }

      router.push({
        pathname: '/itinerary',
        params: {
          data: JSON.stringify(result.structured_itinerary),
          thread_id: result.thread_id,
          start_time: startTime,
          end_time: endTime,
          ...(itineraryId ? { itinerary_id: itineraryId } : {}),
        },
      });
    } catch { setError('Failed to generate. Ensure Agent is running.'); }
    finally { setLoading(false); }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: scale(32) + insets.bottom }]} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Describe Your Ideal Day</Text>
        <TextInput style={styles.textArea} placeholder="E.g. I want to explore heritage sites and eat local food..." placeholderTextColor={Colors.textMuted} multiline numberOfLines={3} value={description} onChangeText={setDescription} />

        <Text style={styles.label}>Interests</Text>
        <View style={styles.chipRow}>
          {INTEREST_TAGS.map(tag => (
            <TouchableOpacity key={tag} style={[styles.chip, selectedInterests.includes(tag) && styles.chipActive]} onPress={() => toggleInterest(tag)}>
              <Text style={[styles.chipText, selectedInterests.includes(tag) && styles.chipTextActive]}>{tag}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Travel Mode</Text>
        <View style={styles.modeRow}>
          {(['walking', 'driving', 'transit'] as const).map(mode => (
            <TouchableOpacity key={mode} style={[styles.modeBtn, travelMode === mode && styles.modeBtnActive]} onPress={() => setTravelMode(mode)}>
              <Text style={styles.modeIcon}>{mode === 'walking' ? '🚶' : mode === 'driving' ? '🚗' : '🚌'}</Text>
              <Text style={[styles.modeText, travelMode === mode && styles.modeTextActive]}>{mode.charAt(0).toUpperCase() + mode.slice(1)}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.timeRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>Start Time</Text>
            <TextInput style={styles.timeInput} value={startTime} onChangeText={setStartTime} placeholder="09:00" placeholderTextColor={Colors.textMuted} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>End Time</Text>
            <TextInput style={styles.timeInput} value={endTime} onChangeText={setEndTime} placeholder="17:00" placeholderTextColor={Colors.textMuted} />
          </View>
        </View>

        <Text style={styles.label}>Trip Dates <Text style={{ color: Colors.textMuted, fontWeight: '400' }}>(optional — for multi-day plans)</Text></Text>
        <View style={styles.timeRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>Start Date</Text>
            <TextInput style={styles.timeInput} value={startDate} onChangeText={setStartDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textMuted} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>End Date</Text>
            <TextInput style={styles.timeInput} value={endDate} onChangeText={setEndDate} placeholder="YYYY-MM-DD" placeholderTextColor={Colors.textMuted} />
          </View>
        </View>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <TouchableOpacity style={[styles.genBtn, loading && { opacity: 0.7 }]} onPress={handleGenerate} disabled={loading}>
          {loading ? (
            <View style={styles.loadingRow}><ActivityIndicator color="white" size="small" /><Text style={styles.genBtnText}>Crafting your itinerary...</Text></View>
          ) : (
            <Text style={styles.genBtnText}>Generate Itinerary ✨</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg, paddingBottom: scale(32) },
  label: { fontSize: scale(12), fontWeight: '600', color: Colors.textPrimary, marginBottom: scale(6), marginTop: Spacing.md },
  textArea: {
    backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.md,
    fontSize: scale(13), color: Colors.textPrimary, textAlignVertical: 'top', minHeight: scale(80),
    borderWidth: 1, borderColor: Colors.border,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { backgroundColor: Colors.white, borderRadius: Radius.full, paddingHorizontal: scale(12), paddingVertical: scale(6), borderWidth: 1, borderColor: Colors.border },
  chipActive: { backgroundColor: Colors.accent, borderColor: Colors.accent },
  chipText: { fontSize: scale(11), fontWeight: '600', color: Colors.textSecondary },
  chipTextActive: { color: Colors.white },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeBtn: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: scale(4),
    backgroundColor: Colors.white, borderRadius: Radius.md, paddingVertical: scale(10),
    borderWidth: 1.5, borderColor: Colors.border,
  },
  modeBtnActive: { borderColor: Colors.accent, backgroundColor: Colors.accentLight },
  modeIcon: { fontSize: scale(14) },
  modeText: { fontSize: scale(11), fontWeight: '600', color: Colors.textSecondary },
  modeTextActive: { color: Colors.accent },
  timeRow: { flexDirection: 'row', gap: Spacing.sm },
  timeInput: {
    backgroundColor: Colors.white, borderRadius: Radius.md, paddingVertical: scale(10),
    fontSize: scale(14), color: Colors.textPrimary, textAlign: 'center', borderWidth: 1, borderColor: Colors.border,
  },
  errorText: { color: Colors.error, fontSize: scale(12), textAlign: 'center', marginTop: Spacing.sm },
  genBtn: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.lg },
  loadingRow: { flexDirection: 'row', alignItems: 'center', gap: scale(8) },
  genBtnText: { color: Colors.white, fontSize: scale(14), fontWeight: '700' },
});
