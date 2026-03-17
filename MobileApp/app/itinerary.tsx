import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity, Linking,
  TextInput, ActivityIndicator, Modal, KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL, getToken } from '@/api/client';

/* ─── Types ─────────────────────────────────────────────── */
interface Stop {
  order?: number; name: string; visit_duration_min?: number;
  short_description?: string; description?: string; google_maps_url?: string;
  travel_to_next?: { duration_text: string; distance_text: string };
}
interface ItineraryData {
  stops: Stop[]; summary?: string; total_duration_min?: number; total_distance?: string;
  start_time?: string;
  end_time?: string;
}
interface PlanMessage { type: 'plan'; version: number; data: ItineraryData; }
interface ChatMessage { type: 'message'; role: 'user' | 'ai'; text: string; }
type ThreadItem = (PlanMessage | ChatMessage) & { id: string };

interface SavedItineraryApi {
  id: string;
  name: string;
  totalDuration?: number;
  generatedNarrative?: string;
  stops?: {
    stopOrder?: number;
    travelTimeMin?: number;
    poi?: { name?: string | null } | null;
  }[];
}

function extractTimeWindowFromText(text: string): { start_time: string; end_time: string } | null {
  const match = text.match(/(\d{1,2}:\d{2}\s?(?:AM|PM)?)\s*[-–]\s*(\d{1,2}:\d{2}\s?(?:AM|PM)?)/i);
  if (!match) return null;
  return {
    start_time: match[1].trim().toUpperCase(),
    end_time: match[2].trim().toUpperCase(),
  };
}

/* ─── Plan Card ─────────────────────────────────────────── */
function PlanCard({
  item, onRate
}: {
  item: PlanMessage & { id: string };
  onRate: (itineraryId: string, verdict: 'good' | 'bad', comment?: string) => Promise<boolean>;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [rated, setRated] = useState(false);
  const [ratingModal, setRatingModal] = useState(false);
  const [pendingVerdict, setPendingVerdict] = useState<'good' | 'bad'>('bad');
  const [comment, setComment] = useState('');
  const d = item.data;

  const submitRating = async () => {
    const ok = await onRate(item.id, pendingVerdict, comment.trim() || undefined);
    if (ok) {
      setRated(true);
      setRatingModal(false);
    }
  };

  const submitGood = async () => {
    const ok = await onRate(item.id, 'good');
    if (ok) setRated(true);
  };

  return (
    <View style={styles.planCard}>
      {/* Plan header */}
      <TouchableOpacity onPress={() => setCollapsed(c => !c)} style={styles.planHeader}>
        <View style={{ flex: 1 }}>
          <Text style={styles.planVersion}>📋 Plan v{item.version}</Text>
          <Text style={styles.planTitle} numberOfLines={1}>{d.summary || 'Penang Itinerary'}</Text>
          <View style={styles.planMeta}>
            {(d.start_time || d.end_time) ? (
              <Text style={styles.planMetaText}>🕘 {d.start_time ?? '—'} - {d.end_time ?? '—'}</Text>
            ) : null}
            <Text style={styles.planMetaText}>⏱️ {d.total_duration_min ? `${Math.round(d.total_duration_min / 60 * 10) / 10}h` : '—'}</Text>
            <Text style={styles.planMetaText}>📍 {d.stops.length} stops</Text>
            <Text style={styles.planMetaText}>🚶 {d.total_distance || '—'}</Text>
          </View>
        </View>
        <Text style={{ fontSize: scale(14), color: '#7c3aed' }}>{collapsed ? '▼' : '▲'}</Text>
      </TouchableOpacity>

      {/* Stops */}
      {!collapsed && d.stops.map((stop, i) => (
        <View key={i}>
          <View style={styles.stopRow}>
            <View style={styles.stopBadge}><Text style={styles.stopBadgeText}>{stop.order ?? i + 1}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.stopName}>{stop.name}</Text>
              {stop.visit_duration_min ? <Text style={styles.stopDur}>⏱️ {stop.visit_duration_min} min</Text> : null}
              {stop.short_description ? <Text style={styles.stopShort} numberOfLines={1}>{stop.short_description}</Text> : null}
              {stop.description ? <Text style={styles.stopDesc} numberOfLines={2}>{stop.description}</Text> : null}
              {stop.google_maps_url ? (
                <TouchableOpacity style={styles.mapLink} onPress={() => Linking.openURL(stop.google_maps_url!)}>
                  <Text style={styles.mapLinkText}>Open in Maps 🗺️</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          </View>
          {stop.travel_to_next && (
            <View style={styles.travelSeg}>
              <View style={styles.travelLine} />
              <Text style={styles.travelText}>🚶 {stop.travel_to_next.duration_text} · {stop.travel_to_next.distance_text}</Text>
            </View>
          )}
        </View>
      ))}

      {/* Rating bar */}
      {!collapsed && (
        <View style={styles.ratingBar}>
          {rated ? (
            <Text style={styles.ratedText}>✅ Thanks for your feedback!</Text>
          ) : (
            <>
              <Text style={styles.rateLabel}>Was this plan helpful?</Text>
              <TouchableOpacity style={styles.verdictBtn} onPress={() => { void submitGood(); }}>
                <Text style={styles.verdictText}>👍 Good</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.verdictBtn} onPress={() => { setPendingVerdict('bad'); setRatingModal(true); }}>
                <Text style={styles.verdictText}>👎 Bad</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      )}

      {/* Rating modal */}
      <Modal visible={ratingModal} transparent animationType="fade" onRequestClose={() => setRatingModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Tell us what was bad 👎</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Optional: what should be improved?"
              placeholderTextColor={Colors.textMuted}
              value={comment}
              onChangeText={setComment}
              multiline
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.modalCancel} onPress={() => setRatingModal(false)}>
                <Text style={{ color: Colors.textSecondary }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSubmit} onPress={() => { void submitRating(); }}>
                <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

/* ─── Main Screen ───────────────────────────────────────── */
export default function ItineraryScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const insets = useSafeAreaInsets();
  const listRef = useRef<FlatList>(null);

  const [messages, setMessages] = useState<ThreadItem[]>(() => {
    let initial: ItineraryData | null = null;
    try { if (params.data && typeof params.data === 'string') initial = JSON.parse(params.data); } catch {}
    if (!initial?.stops) return [];
    initial = {
      ...initial,
      start_time: initial.start_time ?? (params.start_time as string | undefined),
      end_time: initial.end_time ?? (params.end_time as string | undefined),
    };
    return [{ id: 'plan-0', type: 'plan', version: 1, data: initial }];
  });
  const [ratedChatMessages, setRatedChatMessages] = useState<Record<string, 1 | -1>>({});
  const [chatFeedbackModal, setChatFeedbackModal] = useState(false);
  const [chatFeedbackComment, setChatFeedbackComment] = useState('');
  const [pendingBadFeedback, setPendingBadFeedback] = useState<{ messageId: string; aiMessage: string; userMessage?: string } | null>(null);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const threadId = params.thread_id as string | undefined;
  const itineraryIdParam = params.id as string | undefined;
  const itineraryDbId = params.itinerary_id as string | undefined;
  const startTimeParam = params.start_time as string | undefined;
  const endTimeParam = params.end_time as string | undefined;
  const [loadingSaved, setLoadingSaved] = useState(false);

  const versionCount = messages.filter(m => m.type === 'plan').length;

  const pushMsg = (msg: ThreadItem) => setMessages(prev => [...prev, msg]);

  useEffect(() => {
    let isMounted = true;

    const loadSavedItinerary = async () => {
      if (messages.length > 0) return;
      if (!itineraryIdParam) return;

      setLoadingSaved(true);
      try {
        const BASE = API_BASE_URL.replace('/api/v1', '');
        const token = await getToken();
        const response = await fetch(`${BASE}/api/itineraries/${itineraryIdParam}`, {
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });

        if (!response.ok) return;

        const data = await response.json();
        const itinerary: SavedItineraryApi | undefined = data?.itinerary;
        if (!itinerary) return;

        let structuredFromNarrative: ItineraryData | null = null;
        if (typeof itinerary.generatedNarrative === 'string') {
          try {
            const parsed = JSON.parse(itinerary.generatedNarrative);
            if (parsed && Array.isArray(parsed.stops)) {
              structuredFromNarrative = parsed as ItineraryData;
            }
          } catch {
            structuredFromNarrative = null;
          }
        }

        if (structuredFromNarrative) {
          if (!isMounted) return;
          setMessages([{
            id: 'plan-saved-0',
            type: 'plan',
            version: 1,
            data: {
              ...structuredFromNarrative,
              start_time: structuredFromNarrative.start_time ?? startTimeParam,
              end_time: structuredFromNarrative.end_time ?? endTimeParam,
            },
          }]);
          return;
        }

        const stops = Array.isArray(itinerary.stops) ? itinerary.stops : [];

        const mapped: ItineraryData = {
          summary: itinerary.name,
          total_duration_min: itinerary.totalDuration ?? 0,
          start_time: startTimeParam,
          end_time: endTimeParam,
          stops: stops.map((s, idx) => ({
            order: s.stopOrder ?? idx + 1,
            name: s.poi?.name || `Stop ${s.stopOrder ?? idx + 1}`,
            visit_duration_min: s.travelTimeMin ?? 30,
            short_description: '',
            description: '',
          })),
        };

        if (!isMounted) return;
        if (mapped.stops.length > 0) {
          setMessages([{ id: 'plan-saved-0', type: 'plan', version: 1, data: mapped }]);
        } else {
          setMessages([
            { id: 'plan-saved-0', type: 'plan', version: 1, data: mapped },
            {
              id: 'plan-saved-note',
              type: 'message',
              role: 'ai',
              text: 'This saved itinerary has no detailed stops stored yet, but your plan record is loaded successfully.',
            },
          ]);
        }
      } catch {
        // Keep empty-state fallback
      } finally {
        if (isMounted) setLoadingSaved(false);
      }
    };

    void loadSavedItinerary();

    return () => {
      isMounted = false;
    };
  }, [itineraryIdParam, messages.length, startTimeParam, endTimeParam]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput('');
    pushMsg({ id: `user-${Date.now()}`, type: 'message', role: 'user', text });
    setTyping(true);
    listRef.current?.scrollToEnd({ animated: true });

    try {
      const chatRes = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId || (itineraryIdParam ? `itinerary_${itineraryIdParam}` : undefined) }),
      });
      if (!chatRes.ok) throw new Error(`Chat failed (${chatRes.status})`);

      const chatData = await chatRes.json();
      const response: string = chatData.response || '';

      // Try to extract a structured itinerary; if successful → plan card; otherwise → chat bubble
      try {
        const extractRes = await fetch(`${API_BASE_URL}/extract`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ response_text: response, travel_mode: 'walking' }),
        });

        if (extractRes.ok) {
          const extractData = await extractRes.json();
          const structured: ItineraryData | null =
            (extractData?.structured_itinerary && Array.isArray(extractData.structured_itinerary.stops))
              ? extractData.structured_itinerary
              : (Array.isArray(extractData?.stops) ? extractData : null);

          if (structured?.stops?.length) {
            const latestPlan = [...messages].reverse().find(m => m.type === 'plan') as (PlanMessage & { id: string }) | undefined;
            const inferredWindow = extractTimeWindowFromText(response);

            const nextPlan: ItineraryData = {
              ...structured,
              start_time: structured.start_time ?? inferredWindow?.start_time ?? latestPlan?.data.start_time ?? startTimeParam,
              end_time: structured.end_time ?? inferredWindow?.end_time ?? latestPlan?.data.end_time ?? endTimeParam,
            };

            pushMsg({ id: `plan-${Date.now()}`, type: 'plan', version: versionCount + 1, data: nextPlan });
          } else {
            pushMsg({ id: `ai-${Date.now()}`, type: 'message', role: 'ai', text: response });
          }

        } else {
          pushMsg({ id: `ai-${Date.now()}`, type: 'message', role: 'ai', text: response });
        }
      } catch {
        pushMsg({ id: `ai-${Date.now()}`, type: 'message', role: 'ai', text: response });
      }
    } catch {
      pushMsg({ id: `err-${Date.now()}`, type: 'message', role: 'ai', text: 'Sorry, something went wrong. Please try again.' });
    } finally {
      setTyping(false);
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  const handleRate = useCallback(async (planId: string, verdict: 'good' | 'bad', comment?: string) => {
    const dbId = itineraryDbId;
    if (!dbId) {
      Alert.alert('Could not save feedback', 'This itinerary has no saved ID yet. Please generate a new plan and try again.');
      return false;
    }

    const rating = verdict === 'good' ? 5 : 1;

    try {
      const BASE = API_BASE_URL.replace('/api/v1', '');
      const token = await getToken();
      const response = await fetch(`${BASE}/api/v1/feedback/itinerary`, {
        method: 'POST', headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ itineraryId: dbId, rating, comment }),
      });

      if (!response.ok) {
        Alert.alert('Could not save feedback', 'Server rejected the rating. Please try again.');
        return false;
      }

      Alert.alert('Feedback saved', 'Thanks! Your itinerary rating was submitted.');
      return true;
    } catch {
      Alert.alert('Could not save feedback', 'Network error while submitting rating.');
      return false;
    }
  }, [itineraryDbId]);

  const sendChatFeedback = useCallback(async (
    messageId: string,
    rating: 1 | -1,
    aiMessage: string,
    userMessage?: string,
    comment?: string,
  ) => {
    try {
      const BASE = API_BASE_URL.replace('/api/v1', '');
      const token = await getToken();
      const response = await fetch(`${BASE}/api/v1/feedback/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          rating,
          aiMessage,
          userMessage,
          context: 'Itinerary Chat',
          comment,
        }),
      });

      if (!response.ok) return;
      setRatedChatMessages(prev => ({ ...prev, [messageId]: rating }));
    } catch {
      // ignore feedback errors to avoid blocking chat UX
    }
  }, []);

  const submitBadChatFeedback = async () => {
    if (!pendingBadFeedback) return;
    await sendChatFeedback(
      pendingBadFeedback.messageId,
      -1,
      pendingBadFeedback.aiMessage,
      pendingBadFeedback.userMessage,
      chatFeedbackComment.trim() || undefined,
    );
    setChatFeedbackComment('');
    setPendingBadFeedback(null);
    setChatFeedbackModal(false);
  };

  const renderItem = ({ item, index }: { item: ThreadItem; index: number }) => {
    if (item.type === 'plan') {
      return <PlanCard item={item as PlanMessage & { id: string }} onRate={handleRate} />;
    }
    const isUser = item.role === 'user';

    const prevUserMsg = messages
      .slice(0, index)
      .reverse()
      .find(
        m => m.type === 'message' && m.role === 'user' && typeof m.text === 'string' && m.text.trim()
      ) as ChatMessage | undefined;

    return (
      <View style={{ marginBottom: Spacing.sm }}>
        <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
          <Text style={[styles.bubbleText, isUser && { color: Colors.white }]}>{item.text}</Text>
        </View>
        {!isUser && (
          <View style={styles.feedbackRow}>
            {([1, -1] as const).map(r => {
              const voted = ratedChatMessages[item.id];
              const active = voted === r;
              return (
                <TouchableOpacity
                  key={r}
                  disabled={voted !== undefined}
                  onPress={() => {
                    if (r === 1) {
                      void sendChatFeedback(item.id, 1, item.text, prevUserMsg?.text);
                    } else {
                      setPendingBadFeedback({ messageId: item.id, aiMessage: item.text, userMessage: prevUserMsg?.text });
                      setChatFeedbackModal(true);
                    }
                  }}
                  style={[styles.feedbackBtn, active && styles.feedbackBtnActive]}
                >
                  <Text style={{ fontSize: scale(13) }}>{r === 1 ? '👍 Good' : '👎 Bad'}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}
      </View>
    );
  };

  if (loadingSaved) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Colors.accent} />
        <Text style={{ color: Colors.textMuted, fontSize: scale(13), marginTop: 10 }}>Loading itinerary…</Text>
      </View>
    );
  }

  if (messages.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={{ color: Colors.error, fontSize: scale(15), marginBottom: 16 }}>No itinerary found.</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Text style={{ color: Colors.white, fontWeight: '700' }}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + scale(8) }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBack}>
          <Text style={styles.headerBackText}>←</Text>
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Your Itinerary</Text>
          <Text style={styles.headerSub}>{versionCount} plan{versionCount !== 1 ? 's' : ''} · Tap to modify or ask questions</Text>
        </View>
        <TouchableOpacity onPress={() => router.replace('/(tabs)')} style={styles.doneBtn}>
          <Text style={styles.doneBtnText}>✓ Done</Text>
        </TouchableOpacity>
      </View>

      {/* Thread */}
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={item => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.thread}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
      />

      {/* Typing indicator */}
      {typing && (
        <View style={[styles.aiBubble, { marginHorizontal: Spacing.md, marginBottom: Spacing.xs }]}>
          <Text style={styles.bubbleText}>✨ Updating your plan...</Text>
        </View>
      )}

      {/* Quick suggestions */}
      <View style={styles.suggestRow}>
        {['Add more food', 'Make it shorter', 'Add a cafe', 'What time to start?'].map(q => (
          <TouchableOpacity key={q} style={styles.suggestBtn} onPress={() => setInput(q)}>
            <Text style={styles.suggestText}>{q}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Input bar */}
      <View style={[styles.inputBar, { paddingBottom: Spacing.sm + insets.bottom }]}>
        <TextInput
          style={styles.inputField}
          placeholder="Modify plan or ask anything…"
          placeholderTextColor={Colors.textMuted}
          value={input}
          onChangeText={setInput}
          onSubmitEditing={handleSend}
          returnKeyType="send"
        />
        <TouchableOpacity style={styles.sendBtn} onPress={handleSend} disabled={typing}>
          {typing ? <ActivityIndicator color={Colors.white} size="small" /> : <Text style={styles.sendText}>↑</Text>}
        </TouchableOpacity>
      </View>

      <Modal visible={chatFeedbackModal} transparent animationType="fade" onRequestClose={() => setChatFeedbackModal(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>What was bad about this answer? 👎</Text>
            <TextInput
              style={styles.modalInput}
              placeholder="Optional: tell us what should improve"
              placeholderTextColor={Colors.textMuted}
              value={chatFeedbackComment}
              onChangeText={setChatFeedbackComment}
              multiline
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.modalCancel} onPress={() => setChatFeedbackModal(false)}>
                <Text style={{ color: Colors.textSecondary }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSubmit} onPress={() => { void submitBadChatFeedback(); }}>
                <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.lg },
  backBtn: { backgroundColor: Colors.primary, borderRadius: Radius.md, paddingVertical: scale(10), paddingHorizontal: Spacing.lg },

  // Header
  header: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.md, paddingBottom: Spacing.sm, flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  headerBack: { width: scale(34), height: scale(34), borderRadius: scale(17), backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  headerBackText: { fontSize: scale(18), color: Colors.white, fontWeight: '700' },
  headerTitle: { fontSize: scale(15), fontWeight: '800', color: Colors.white },
  headerSub: { fontSize: scale(10), color: 'rgba(255,255,255,0.65)', marginTop: scale(1) },
  doneBtn: { backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(12) },
  doneBtnText: { color: Colors.white, fontWeight: '700', fontSize: scale(12) },

  // Thread
  thread: { padding: Spacing.md, paddingBottom: Spacing.sm, gap: Spacing.sm },

  // Plan card
  planCard: { backgroundColor: Colors.white, borderRadius: Radius.lg, borderWidth: 1.5, borderColor: '#7c3aed22', marginVertical: scale(4), overflow: 'hidden' },
  planHeader: { flexDirection: 'row', alignItems: 'flex-start', padding: Spacing.md, backgroundColor: '#7c3aed0a' },
  planVersion: { fontSize: scale(10), color: '#7c3aed', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5 },
  planTitle: { fontSize: scale(14), fontWeight: '800', color: Colors.textPrimary, marginTop: scale(2) },
  planMeta: { flexDirection: 'row', gap: Spacing.md, marginTop: scale(4) },
  planMetaText: { fontSize: scale(11), color: Colors.textMuted, fontWeight: '500' },

  stopRow: { flexDirection: 'row', padding: Spacing.sm, gap: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border },
  stopBadge: { width: scale(24), height: scale(24), borderRadius: scale(12), backgroundColor: '#7c3aed', justifyContent: 'center', alignItems: 'center', flexShrink: 0, marginTop: scale(2) },
  stopBadgeText: { color: Colors.white, fontWeight: '800', fontSize: scale(11) },
  stopName: { fontSize: scale(13), fontWeight: '700', color: Colors.textPrimary },
  stopDur: { fontSize: scale(11), color: Colors.textMuted, marginTop: scale(1) },
  stopShort: { fontSize: scale(11), color: '#7c3aed', marginTop: scale(2), fontWeight: '500' },
  stopDesc: { fontSize: scale(11), color: Colors.textSecondary, lineHeight: scale(16), marginTop: scale(2) },
  mapLink: { marginTop: scale(6), backgroundColor: '#EFF6FF', paddingVertical: scale(6), borderRadius: Radius.sm, alignItems: 'center' },
  mapLinkText: { color: '#2563EB', fontWeight: '600', fontSize: scale(10) },
  travelSeg: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, paddingLeft: scale(40), paddingVertical: scale(4), borderTopWidth: 1, borderTopColor: Colors.border },
  travelLine: { width: 2, height: scale(14), backgroundColor: '#7c3aed' },
  travelText: { fontSize: scale(10), color: Colors.textMuted, fontWeight: '500' },

  ratingBar: { flexDirection: 'row', alignItems: 'center', gap: scale(6), padding: Spacing.sm, borderTopWidth: 1, borderTopColor: Colors.border, backgroundColor: '#fafafa' },
  rateLabel: { fontSize: scale(11), color: Colors.textMuted, flex: 1 },
  ratedText: { fontSize: scale(12), color: '#22c55e', fontWeight: '600' },
  verdictBtn: { borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(10), backgroundColor: Colors.white },
  verdictText: { fontSize: scale(11), color: Colors.textPrimary, fontWeight: '600' },

  // Rating modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalBox: { backgroundColor: Colors.white, borderTopLeftRadius: Radius.xl, borderTopRightRadius: Radius.xl, padding: Spacing.lg, paddingBottom: scale(36) },
  modalTitle: { fontSize: scale(16), fontWeight: '800', color: Colors.textPrimary, marginBottom: Spacing.md },
  modalInput: { backgroundColor: Colors.inputBg, borderRadius: Radius.md, padding: Spacing.sm, fontSize: scale(13), color: Colors.textPrimary, minHeight: scale(60), textAlignVertical: 'top', marginBottom: Spacing.md },
  modalButtons: { flexDirection: 'row', gap: Spacing.sm },
  modalCancel: { flex: 1, padding: Spacing.sm, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  modalSubmit: { flex: 1, padding: Spacing.sm, borderRadius: Radius.md, backgroundColor: '#7c3aed', alignItems: 'center' },

  // Chat bubbles
  bubble: { padding: scale(10), borderRadius: Radius.lg, maxWidth: '80%', marginVertical: scale(2) },
  userBubble: { backgroundColor: Colors.primary, alignSelf: 'flex-end', borderBottomRightRadius: scale(4) },
  aiBubble: { backgroundColor: Colors.white, alignSelf: 'flex-start', borderBottomLeftRadius: scale(4), borderWidth: 1, borderColor: Colors.border },
  bubbleText: { fontSize: scale(13), color: Colors.textPrimary, lineHeight: scale(19) },
  feedbackRow: { flexDirection: 'row', gap: scale(6), marginTop: scale(3), paddingLeft: scale(4) },
  feedbackBtn: { paddingHorizontal: scale(8), paddingVertical: scale(3), borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.white },
  feedbackBtnActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },

  // Suggestions + input
  suggestRow: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
  suggestBtn: { backgroundColor: Colors.white, borderRadius: Radius.full, paddingVertical: scale(5), paddingHorizontal: scale(10), borderWidth: 1, borderColor: Colors.border },
  suggestText: { fontSize: scale(10), color: Colors.textPrimary, fontWeight: '500' },
  inputBar: { flexDirection: 'row', padding: Spacing.sm, backgroundColor: Colors.white, borderTopWidth: 1, borderTopColor: Colors.border, gap: Spacing.sm },
  inputField: { flex: 1, backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingHorizontal: Spacing.md, paddingVertical: scale(8), fontSize: scale(13), color: Colors.textPrimary },
  sendBtn: { width: scale(36), height: scale(36), borderRadius: scale(18), backgroundColor: '#7c3aed', justifyContent: 'center', alignItems: 'center' },
  sendText: { color: Colors.white, fontSize: scale(16), fontWeight: '700' },
});
