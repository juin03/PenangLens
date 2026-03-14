import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking, TextInput, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL } from '@/api/client';

export default function ItineraryScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const [refinementInput, setRefinementInput] = useState('');
  const [refining, setRefining] = useState(false);
  const [showRefine, setShowRefine] = useState(false);

  let itineraryData: any = null;
  try { if (params.data && typeof params.data === 'string') itineraryData = JSON.parse(params.data); } catch {}
  const threadId = params.thread_id as string;

  if (!itineraryData || !itineraryData.stops) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>No itinerary data found.</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={styles.backBtnText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const { stops, summary, total_duration_min, total_distance } = itineraryData;

  const handleRefine = async () => {
    if (!refinementInput.trim()) return;
    setRefining(true);
    try {
      const chatRes = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: refinementInput, thread_id: threadId }),
      });
      const chatData = await chatRes.json();
      const extractRes = await fetch(`${API_BASE_URL}/extract`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ response_text: chatData.response, travel_mode: 'walking' }),
      });
      const extractData = await extractRes.json();
      if (extractData.structured_itinerary) router.setParams({ data: JSON.stringify(extractData.structured_itinerary) });
      setRefinementInput(''); setShowRefine(false);
    } catch { alert('Refinement failed.'); }
    finally { setRefining(false); }
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Summary */}
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle} numberOfLines={2}>{summary || 'Your Penang Itinerary'}</Text>
          <View style={styles.statsRow}>
            <View style={styles.stat}><Text style={styles.statVal}>⏱️ {total_duration_min ? `${Math.round(total_duration_min / 60 * 10) / 10}h` : '—'}</Text><Text style={styles.statLbl}>Duration</Text></View>
            <View style={styles.stat}><Text style={styles.statVal}>📍 {stops.length}</Text><Text style={styles.statLbl}>Stops</Text></View>
            <View style={styles.stat}><Text style={styles.statVal}>🚶 {total_distance || '—'}</Text><Text style={styles.statLbl}>Distance</Text></View>
          </View>
        </View>

        {/* Stops */}
        {stops.map((stop: any, i: number) => (
          <View key={i}>
            <View style={styles.stopCard}>
              <View style={styles.stopHeader}>
                <View style={styles.badge}><Text style={styles.badgeText}>{stop.order || i + 1}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.stopName} numberOfLines={1}>{stop.name}</Text>
                  <Text style={styles.stopDur}>⏱️ {stop.visit_duration_min} min</Text>
                </View>
              </View>
              <Text style={styles.stopShort} numberOfLines={2}>{stop.short_description}</Text>
              <Text style={styles.stopDesc} numberOfLines={3}>{stop.description}</Text>
              {stop.google_maps_url && (
                <TouchableOpacity style={styles.mapLink} onPress={() => Linking.openURL(stop.google_maps_url)}>
                  <Text style={styles.mapLinkText}>Open in Maps 🗺️</Text>
                </TouchableOpacity>
              )}
            </View>
            {stop.travel_to_next && (
              <View style={styles.travelSeg}>
                <View style={styles.travelLine} />
                <Text style={styles.travelText}>🚶 {stop.travel_to_next.duration_text} · {stop.travel_to_next.distance_text}</Text>
              </View>
            )}
          </View>
        ))}

        {/* Refine */}
        {!showRefine ? (
          <TouchableOpacity style={styles.refineToggle} onPress={() => setShowRefine(true)}>
            <Text style={styles.refineToggleText}>✏️ Refine Your Itinerary</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.refinePanel}>
            <Text style={styles.refinePanelTitle}>Refine Your Itinerary</Text>
            <View style={styles.quickRow}>
              {['Add more food', 'Add cafe', 'Shorter trip'].map(a => (
                <TouchableOpacity key={a} style={styles.quickBtn} onPress={() => setRefinementInput(a)}>
                  <Text style={styles.quickText}>{a}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.refInputRow}>
              <TextInput style={styles.refInput} placeholder="Or type changes..." placeholderTextColor={Colors.textMuted} value={refinementInput} onChangeText={setRefinementInput} />
              <TouchableOpacity style={styles.sendBtn} onPress={handleRefine} disabled={refining}>
                {refining ? <ActivityIndicator color="white" size="small" /> : <Text style={styles.sendText}>↑</Text>}
              </TouchableOpacity>
            </View>
          </View>
        )}

        <TouchableOpacity style={styles.doneBtn} onPress={() => router.replace('/(tabs)')}>
          <Text style={styles.doneBtnText}>Save & Go Home</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.md, paddingBottom: scale(32) },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.lg },
  errorText: { fontSize: scale(16), color: Colors.error, marginBottom: Spacing.md },
  backBtn: { backgroundColor: Colors.primary, borderRadius: Radius.md, paddingVertical: scale(10), paddingHorizontal: Spacing.lg },
  backBtnText: { color: Colors.white, fontWeight: '700', fontSize: scale(13) },
  summaryCard: { backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.md, marginBottom: Spacing.md, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 6, elevation: 3 },
  summaryTitle: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm },
  statsRow: { flexDirection: 'row', justifyContent: 'space-around' },
  stat: { alignItems: 'center' },
  statVal: { fontSize: scale(13), fontWeight: '700', color: Colors.primary },
  statLbl: { fontSize: scale(10), color: Colors.textMuted, marginTop: scale(2) },
  stopCard: { backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.md, marginBottom: scale(2), borderWidth: 1, borderColor: Colors.border },
  stopHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.xs },
  badge: { backgroundColor: Colors.accent, width: scale(26), height: scale(26), borderRadius: scale(13), justifyContent: 'center', alignItems: 'center' },
  badgeText: { color: Colors.white, fontWeight: 'bold', fontSize: scale(12) },
  stopName: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary },
  stopDur: { fontSize: scale(11), color: Colors.textSecondary, marginTop: scale(1) },
  stopShort: { fontSize: scale(12), fontWeight: '500', color: Colors.primaryLight, marginBottom: scale(3) },
  stopDesc: { fontSize: scale(12), color: Colors.textSecondary, lineHeight: scale(17) },
  mapLink: { marginTop: Spacing.sm, backgroundColor: '#EFF6FF', paddingVertical: scale(8), borderRadius: Radius.sm, alignItems: 'center' },
  mapLinkText: { color: '#2563EB', fontWeight: '600', fontSize: scale(11) },
  travelSeg: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, paddingLeft: Spacing.lg, paddingVertical: scale(6) },
  travelLine: { width: 2, height: scale(18), backgroundColor: Colors.accent },
  travelText: { fontSize: scale(11), color: Colors.textMuted, fontWeight: '500' },
  refineToggle: { backgroundColor: Colors.primary, borderRadius: Radius.lg, paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.md },
  refineToggleText: { color: Colors.white, fontSize: scale(13), fontWeight: '700' },
  refinePanel: { backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.md, marginTop: Spacing.md, borderWidth: 1, borderColor: Colors.accent },
  refinePanelTitle: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm },
  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.xs, marginBottom: Spacing.sm },
  quickBtn: { backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(10) },
  quickText: { fontSize: scale(11), color: Colors.textPrimary, fontWeight: '500' },
  refInputRow: { flexDirection: 'row', gap: Spacing.sm },
  refInput: { flex: 1, backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingHorizontal: Spacing.md, paddingVertical: scale(8), fontSize: scale(12), color: Colors.textPrimary },
  sendBtn: { width: scale(34), height: scale(34), borderRadius: scale(17), backgroundColor: Colors.accent, justifyContent: 'center', alignItems: 'center' },
  sendText: { color: Colors.white, fontSize: scale(16), fontWeight: '700' },
  doneBtn: { backgroundColor: Colors.success, borderRadius: Radius.full, paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.lg },
  doneBtnText: { color: Colors.white, fontSize: scale(14), fontWeight: '700' },
});
