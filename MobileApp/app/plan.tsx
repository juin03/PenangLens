import { useState, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Slider from '@react-native-community/slider';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Colors, Radius, Spacing, scale, Shadow } from '@/constants/theme';
import { saveItinerary, API_BASE_URL, getToken } from '@/api/client';
import { INTEREST_TAGS } from '@/constants/taxonomy';

const toMinutes = (t: string) => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
const toTime = (m: number) => { const h = Math.floor(m / 60); const mm = m % 60; return `${String(h).padStart(2,'0')}:${String(mm).padStart(2,'0')}`; };

export default function PlanTripScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [description, setDescription] = useState('');
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [startTime, setStartTime] = useState('09:00');
  const [endTime, setEndTime] = useState('17:00');
  const [showStartPicker, setShowStartPicker] = useState(false);
  const [showEndPicker, setShowEndPicker] = useState(false);
  const [travelMode, setTravelMode] = useState<'walking' | 'driving' | 'transit'>('walking');
  const [startLocation, setStartLocation] = useState('');
  const [locationInput, setLocationInput] = useState('');
  const [locationSuggestions, setLocationSuggestions] = useState<{ description: string; place_id: string }[]>([]);
  const locationDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Google Places session token: one token per search session (keystrokes + the final
  // details call) so Google bills it as a single session instead of per keystroke.
  const placesSession = useRef<string | null>(null);

  const getPlacesSession = () => {
    if (!placesSession.current) {
      placesSession.current = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    }
    return placesSession.current;
  };

  // Autocomplete goes through the BFF proxy (server-side key + user auth) — the app
  // ships no Places-capable API key.
  const fetchSuggestions = (text: string) => {
    setLocationInput(text);
    if (locationDebounce.current) clearTimeout(locationDebounce.current);
    if (text.length < 2) { setLocationSuggestions([]); return; }
    locationDebounce.current = setTimeout(async () => {
      try {
        const token = await getToken();
        const url = `${API_BASE_URL}/places/autocomplete?input=${encodeURIComponent(text)}&sessiontoken=${getPlacesSession()}`;
        const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
        const data = await res.json();
        setLocationSuggestions(data.predictions ?? []);
      } catch { setLocationSuggestions([]); }
    }, 300);
  };

  const selectLocation = async (item: { description: string; place_id: string }) => {
    setLocationInput(item.description);
    setLocationSuggestions([]);
    try {
      const token = await getToken();
      const url = `${API_BASE_URL}/places/details?place_id=${encodeURIComponent(item.place_id)}&sessiontoken=${getPlacesSession()}`;
      const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      const data = await res.json();
      const loc = data.location;
      setStartLocation(loc ? `${loc.lat},${loc.lng}` : item.description);
    } catch { setStartLocation(item.description); }
    placesSession.current = null; // details call ends the billing session
  };
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const toggleInterest = (tag: string) =>
    setSelectedInterests(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);

  const handleGenerate = async () => {
    if (!description.trim()) { setError('Please describe what you want to do.'); return; }
    setLoading(true); setError(''); setStatus('Planning your itinerary...');

    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          description,
          interests: selectedInterests,
          start_time: startTime,
          end_time: endTime,
          start_location: startLocation.trim() || 'George Town, Penang',
          travel_mode: travelMode,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const result = await res.json();
      const structured = result.structured_itinerary;

      let itineraryId: string | undefined;
      try {
        const saved = await saveItinerary({
          name: structured?.summary || 'My Penang Trip',
          originalPrompt: description,
          generatedNarrative: JSON.stringify(structured),
          totalDuration: structured?.total_duration_min,
          threadId: result.thread_id,
          stops: structured?.stops?.map((s: any, i: number) => ({
            stopOrder: i + 1,
            travelTimeMin: s.travel_to_next?.duration_min,
            name: s.name,
          })),
        });
        itineraryId = saved?.itinerary?.id;
      } catch {}

      router.push({
        pathname: '/itinerary',
        params: {
          data: JSON.stringify(structured),
          thread_id: result.thread_id,
          start_time: startTime,
          end_time: endTime,
          ...(itineraryId ? { itinerary_id: itineraryId } : {}),
        },
      });
    } catch (err) {
      setError('Failed to generate. Please try again.');
    } finally {
      setLoading(false);
      setStatus('');
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: Colors.background }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + scale(8) }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBack}>
          <Text style={styles.headerBackText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Plan Your Trip</Text>
        <View style={{ width: scale(36) }} />
      </View>

      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: scale(32) + insets.bottom }]} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Starting Location <Text style={{ color: Colors.tabInactive, fontWeight: '400' }}>(optional)</Text></Text>
        <TextInput
          style={styles.timeInput}
          value={locationInput}
          onChangeText={fetchSuggestions}
          placeholder="Default: George Town, Penang"
          placeholderTextColor={Colors.tabInactive}
        />
        {locationSuggestions.length > 0 && (
          <View style={{ borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.md, marginTop: -8, marginBottom: 8, backgroundColor: Colors.white }}>
            {locationSuggestions.map((item, i) => (
              <TouchableOpacity key={item.place_id} onPress={() => selectLocation(item)}
                style={{ padding: scale(10), borderBottomWidth: i < locationSuggestions.length - 1 ? 1 : 0, borderBottomColor: Colors.border }}>
                <Text style={{ fontSize: scale(13), color: Colors.textPrimary }}>{item.description}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

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
          {(['walking', 'driving'] as const).map(mode => (
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

        <Text style={styles.label}>Time Range</Text>
        <View style={{ flexDirection: 'row', gap: scale(10), marginBottom: scale(10) }}>
          <TouchableOpacity onPress={() => setShowStartPicker(true)}
            style={{ flex: 1, backgroundColor: Colors.white, borderRadius: Radius.md, paddingVertical: scale(8), paddingHorizontal: scale(12), borderWidth: 1, borderColor: Colors.border, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontSize: scale(11), color: Colors.textMuted }}>Start</Text>
            <Text style={{ fontSize: scale(15), fontWeight: '700', color: Colors.primary }}>{startTime}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => setShowEndPicker(true)}
            style={{ flex: 1, backgroundColor: Colors.white, borderRadius: Radius.md, paddingVertical: scale(8), paddingHorizontal: scale(12), borderWidth: 1, borderColor: Colors.border, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={{ fontSize: scale(11), color: Colors.textMuted }}>End</Text>
            <Text style={{ fontSize: scale(15), fontWeight: '700', color: Colors.primary }}>{endTime}</Text>
          </TouchableOpacity>
        </View>
        {showStartPicker && (
          <DateTimePicker
            mode="time" minuteInterval={15} is24Hour
            value={(() => { const [h,m] = startTime.split(':').map(Number); const d = new Date(); d.setHours(h,m,0,0); return d; })()}
            onChange={(_, d) => { setShowStartPicker(false); if (d) setStartTime(toTime(d.getHours()*60+d.getMinutes())); }}
          />
        )}
        {showEndPicker && (
          <DateTimePicker
            mode="time" minuteInterval={15} is24Hour
            value={(() => { const [h,m] = endTime.split(':').map(Number); const d = new Date(); d.setHours(h,m,0,0); return d; })()}
            onChange={(_, d) => { setShowEndPicker(false); if (d) setEndTime(toTime(d.getHours()*60+d.getMinutes())); }}
          />
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

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
  container: { flex: 1, backgroundColor: Colors.background },
  header: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    backgroundColor: Colors.white, 
    paddingHorizontal: Spacing.md, 
    paddingBottom: scale(12),
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  headerBack: { width: scale(36), height: scale(36), borderRadius: scale(18), backgroundColor: Colors.background, justifyContent: 'center', alignItems: 'center' },
  headerBackText: { fontSize: scale(20), color: Colors.primary, fontWeight: '700' },
  headerTitle: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary },
  content: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.sm },
  label: { 
    fontSize: scale(13), 
    fontWeight: '700', 
    color: Colors.textPrimary, 
    marginBottom: Spacing.sm, 
    marginTop: Spacing.md 
  },
  textArea: { 
    backgroundColor: Colors.white, 
    borderRadius: Radius.md, 
    padding: Spacing.md, 
    color: Colors.textPrimary, 
    fontSize: scale(14), 
    minHeight: scale(100), 
    textAlignVertical: 'top',
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  chip: { 
    backgroundColor: Colors.white, 
    borderRadius: Radius.full, 
    paddingVertical: scale(8), 
    paddingHorizontal: scale(16), 
    borderWidth: 1, 
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  chipActive: { 
    backgroundColor: Colors.accentLight, 
    borderColor: Colors.accent,
    shadowOpacity: 0,
    elevation: 0,
  },
  chipText: { fontSize: scale(12), color: Colors.textSecondary, fontWeight: '500' },
  chipTextActive: { color: Colors.accentDark, fontWeight: '700' },
  modeRow: { flexDirection: 'row', gap: Spacing.sm },
  modeBtn: { 
    flex: 1, 
    backgroundColor: Colors.white, 
    borderRadius: Radius.md, 
    padding: Spacing.md, 
    alignItems: 'center', 
    borderWidth: 1, 
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  modeBtnActive: { 
    backgroundColor: Colors.accentLight, 
    borderColor: Colors.accent,
    shadowOpacity: 0,
    elevation: 0,
  },
  modeIcon: { fontSize: scale(24), marginBottom: scale(4) },
  modeText: { fontSize: scale(11), color: Colors.textSecondary, fontWeight: '500' },
  modeTextActive: { color: Colors.accentDark, fontWeight: '700' },
  timeRow: { flexDirection: 'row', gap: Spacing.md },
  timeInput: { 
    flex: 1,
    backgroundColor: Colors.white, 
    borderRadius: Radius.md, 
    padding: Spacing.md, 
    color: Colors.textPrimary, 
    fontSize: scale(14),
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  timeChip: {
    paddingHorizontal: scale(12), paddingVertical: scale(8), borderRadius: Radius.md,
    borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.white,
  },
  timeChipActive: { backgroundColor: Colors.accent, borderColor: Colors.accent },
  timeChipText: { fontSize: scale(13), color: Colors.textPrimary, fontWeight: '500' },
  timeChipTextActive: { color: Colors.white },
  error: { color: Colors.error, fontSize: scale(12), marginTop: Spacing.sm },
  generateBtn: { 
    backgroundColor: Colors.accent, 
    borderRadius: Radius.lg, 
    paddingVertical: scale(16), 
    alignItems: 'center', 
    marginTop: Spacing.xl,
    ...Shadow.md,
  },
  generateBtnDisabled: { opacity: 0.6 },
  generateText: { color: Colors.white, fontSize: scale(16), fontWeight: '800' },
  loadingContainer: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  statusBox: {
    padding: scale(16),
    backgroundColor: 'rgba(27,58,75,0.05)',
    borderRadius: Radius.md,
    marginTop: Spacing.lg,
    borderWidth: 1,
    borderColor: 'rgba(27,58,75,0.1)',
  },
  statusText: { color: Colors.primary, fontSize: scale(14), textAlign: 'center', fontWeight: '500' },
});

