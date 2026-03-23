import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { saveItinerary } from '@/api/client';
import { streamItinerary } from '@/api/streaming';
import { INTEREST_TAGS } from '@/constants/taxonomy';

export default function PlanTripScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [description, setDescription] = useState('');
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('17:00');
  const [travelMode, setTravelMode] = useState<'walking' | 'driving' | 'transit'>('walking');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const toggleInterest = (tag: string) =>
    setSelectedInterests(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);

  const handleGenerate = async () => {
    if (!description.trim()) { setError('Please describe what you want to do.'); return; }
    setLoading(true); setError(''); setStatus('');
    
    try {
      const stream = streamItinerary({
        description,
        interests: selectedInterests,
        start_time: startTime,
        end_time: endTime,
        start_location: 'George Town, Penang',
        travel_mode: travelMode,
      });

      for await (const update of stream) {
        if (update.type === 'status') {
          setStatus(update.message || '');
        } else if (update.type === 'complete') {
          const result = update.data;
          
          // Save to DB
          let itineraryId: string | undefined;
          try {
            const structured = result.structured;
            const saved = await saveItinerary({
              name: structured?.summary || 'My Penang Trip',
              originalPrompt: description,
              generatedNarrative: JSON.stringify(structured),
              totalDuration: structured?.total_duration_min,
              threadId: result.thread_id,
            });
            itineraryId = saved?.itinerary?.id;
          } catch {}

          // Navigate to result
          router.push({
            pathname: '/itinerary',
            params: {
              data: JSON.stringify(result.structured),
              thread_id: result.thread_id,
              start_time: startTime,
              end_time: endTime,
              ...(itineraryId ? { itinerary_id: itineraryId } : {}),
            },
          });
          break;
        } else if (update.type === 'error') {
          setError(update.message || 'Generation failed');
          break;
        }
      }
    } catch (err) {
      setError('Failed to generate. Ensure Agent is running.');
    } finally {
      setLoading(false);
      setStatus('');
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: scale(32) + insets.bottom }]} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Describe Your Ideal Day</Text>
        <TextInput 
          style={styles.textArea} 
          placeholder="E.g. I want to explore heritage sites and eat local food..." 
          placeholderTextColor={Colors.tabInactive} 
          multiline 
          numberOfLines={3} 
          value={description} 
          onChangeText={setDescription} 
        />

        <Text style={styles.label}>Interests</Text>
        <View style={styles.chipRow}>
          {INTEREST_TAGS.map(tag => (
            <TouchableOpacity 
              key={tag} 
              style={[styles.chip, selectedInterests.includes(tag) && styles.chipActive]} 
              onPress={() => toggleInterest(tag)}
            >
              <Text style={[styles.chipText, selectedInterests.includes(tag) && styles.chipTextActive]}>{tag}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Travel Mode</Text>
        <View style={styles.modeRow}>
          {(['walking', 'driving', 'transit'] as const).map(mode => (
            <TouchableOpacity 
              key={mode} 
              style={[styles.modeBtn, travelMode === mode && styles.modeBtnActive]} 
              onPress={() => setTravelMode(mode)}
            >
              <Text style={styles.modeIcon}>{mode === 'walking' ? '🚶' : mode === 'driving' ? '🚗' : '🚌'}</Text>
              <Text style={[styles.modeText, travelMode === mode && styles.modeTextActive]}>
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.timeRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>Start Time</Text>
            <TextInput 
              style={styles.timeInput} 
              value={startTime} 
              onChangeText={setStartTime} 
              placeholder="09:00" 
              placeholderTextColor={Colors.tabInactive} 
            />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.label}>End Time</Text>
            <TextInput 
              style={styles.timeInput} 
              value={endTime} 
              onChangeText={setEndTime} 
              placeholder="17:00" 
              placeholderTextColor={Colors.tabInactive} 
            />
          </View>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
        
        {loading && status ? (
          <View style={{ padding: scale(16), backgroundColor: Colors.primary + '20', borderRadius: Radius.m, marginBottom: scale(16) }}>
            <Text style={{ color: Colors.primary, fontSize: scale(14), textAlign: 'center' }}>{status}</Text>
          </View>
        ) : null}

        <TouchableOpacity 
          style={[styles.generateBtn, loading && styles.generateBtnDisabled]} 
          onPress={handleGenerate} 
          disabled={loading}
        >
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator color={Colors.white} size="small" />
              <Text style={styles.generateText}>{status || 'Generating...'}</Text>
            </View>
          ) : (
            <Text style={styles.generateText}>✨ Generate Itinerary</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.primary },
  content: { padding: Spacing.lg },
  label: { fontSize: scale(12), fontWeight: '600', color: Colors.tabInactive, marginBottom: Spacing.sm, marginTop: Spacing.md },
  textArea: { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: Radius.md, padding: Spacing.md, color: Colors.white, fontSize: scale(14), minHeight: scale(80), textAlignVertical: 'top' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(12), borderWidth: 1, borderColor: 'transparent' },
  chipActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },
  chipText: { fontSize: scale(12), color: Colors.white, fontWeight: '500' },
  chipTextActive: { color: Colors.accent, fontWeight: '700' },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeBtn: { flex: 1, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: Radius.md, padding: Spacing.md, alignItems: 'center', borderWidth: 2, borderColor: 'transparent' },
  modeBtnActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },
  modeIcon: { fontSize: scale(24), marginBottom: scale(4) },
  modeText: { fontSize: scale(11), color: Colors.white, fontWeight: '500' },
  modeTextActive: { color: Colors.accent, fontWeight: '700' },
  timeRow: { flexDirection: 'row', gap: Spacing.md },
  timeInput: { backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: Radius.md, padding: Spacing.md, color: Colors.white, fontSize: scale(14) },
  error: { color: Colors.error, fontSize: scale(12), marginTop: Spacing.sm },
  generateBtn: { backgroundColor: Colors.accent, borderRadius: Radius.lg, paddingVertical: scale(14), alignItems: 'center', marginTop: Spacing.xl },
  generateBtnDisabled: { opacity: 0.6 },
  generateText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },
  loadingContainer: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
});
