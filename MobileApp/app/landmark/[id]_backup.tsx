import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, FlatList, ActivityIndicator, Image, Dimensions, Modal,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL, chatWithAgent, getToken } from '@/api/client';

const { width: SCREEN_W } = Dimensions.get('window');
const HERO_H = scale(240);

type TabType = 'overview' | 'details' | 'chat';
interface ChatMsg { role: 'user' | 'assistant'; content: string; }

interface SpotImage { id: string; url: string; filename: string; }

interface SpotDetail {
  id: string;
  name: string;
  type: string;
  description?: string;
  content?: { overview?: string; history?: string; culture?: string; funFacts?: string };
  tags?: string[];
  images?: SpotImage[];
  lat?: number;
  lng?: number;
}

export default function SpotDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const insets = useSafeAreaInsets();
  const flatRef = useRef<FlatList>(null);

  const spotId = typeof params.id === 'string' ? params.id : '';
  const nameParam = typeof params.name === 'string' ? params.name : 'Landmark';

  const [spot, setSpot] = useState<SpotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [heroIdx, setHeroIdx] = useState(0);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: `Hi! Ask me anything about ${nameParam}.` },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  const [ratedMessages, setRatedMessages] = useState<Record<number, 1 | -1>>({});
  const [feedbackModalVisible, setFeedbackModalVisible] = useState(false);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [pendingBadFeedback, setPendingBadFeedback] = useState<{ idx: number; aiMessage: string; userMessage?: string } | null>(null);

  const sendChatFeedback = async (idx: number, rating: 1 | -1, aiMessage: string, userMessage?: string, comment?: string) => {
    const BASE = API_BASE_URL.replace('/api/v1', '');
    try {
      const token = await getToken();
      const res = await fetch(`${BASE}/api/v1/feedback/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ rating, aiMessage, userMessage, context: displayName, comment }),
      });

      if (!res.ok) throw new Error(`Feedback save failed (${res.status})`);
      setRatedMessages(prev => ({ ...prev, [idx]: rating }));
    } catch (error) {
      console.warn('Failed to submit chat feedback:', error);
    }
  };

  const submitBadFeedback = async () => {
    if (!pendingBadFeedback) return;
    await sendChatFeedback(
      pendingBadFeedback.idx,
      -1,
      pendingBadFeedback.aiMessage,
      pendingBadFeedback.userMessage,
      feedbackComment.trim() || undefined,
    );
    setFeedbackComment('');
    setPendingBadFeedback(null);
    setFeedbackModalVisible(false);
  };

  // ── Load spot from BFF ────────────────────────────────────
  useEffect(() => {
    if (!spotId) { setLoading(false); return; }
    (async () => {
      try {
        const BASE = API_BASE_URL.replace('/api/v1', '');
        const res = await fetch(`${BASE}/api/admin/spots/${spotId}`);
        if (res.ok) {
          const data = await res.json();
          setSpot(data.spot);
        }
      } catch { /* silent */ }
      finally { setLoading(false); }
    })();
  }, [spotId]);

  // ── Agent chat ─────────────────────────────────────────────
  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    try {
      const data = await chatWithAgent({
        message: `[About ${spot?.name ?? nameParam}] ${userMsg}`,
        thread_id: threadId ?? `spot_${spotId}`,
      });
      setThreadId(data.thread_id);
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response || 'Sorry, I could not answer that.' }]);
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: 'Connection error. Please try again.' }]);
    } finally { setChatLoading(false); }
  };

  const displayName = spot?.name ?? nameParam;
  const content = spot?.content;
  const images = spot?.images ?? [];
  const BASE_URL = API_BASE_URL.replace('/api/v1', '');

  const resolveImageUrl = (url: string) => {
    if (!url) return null;
    if (url.startsWith('http')) return url;
    return `${BASE_URL}${url}`;
  };

  if (loading) {
    return (
      <View style={[styles.container, { justifyContent: 'center', alignItems: 'center' }]}>
        <ActivityIndicator size="large" color={Colors.accent} />
        <Text style={{ marginTop: scale(12), color: Colors.textMuted, fontSize: scale(13) }}>Loading...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* ── Hero Image Carousel ── */}
      <View style={styles.heroContainer}>
        {images.length > 0 ? (
          <>
            <ScrollView
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              onMomentumScrollEnd={e => {
                const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
                setHeroIdx(idx);
              }}
            >
              {images.map((img, i) => {
                const uri = resolveImageUrl(img.url);
                return uri ? (
                  <Image
                    key={img.id}
                    source={{ uri }}
                    style={styles.heroImage}
                    resizeMode="cover"
                  />
                ) : (
                  <View key={img.id} style={[styles.heroImage, styles.heroPlaceholder]}>
                    <Text style={styles.heroPlaceholderText}>🏛️</Text>
                  </View>
                );
              })}
            </ScrollView>
            {/* Pagination dots */}
            {images.length > 1 && (
              <View style={styles.dotsRow}>
                {images.map((_, i) => (
                  <View key={i} style={[styles.dot, i === heroIdx && styles.dotActive]} />
                ))}
              </View>
            )}
          </>
        ) : (
          <View style={[styles.heroImage, styles.heroPlaceholder]}>
            <Text style={styles.heroPlaceholderText}>{spot?.type === 'landmark' ? '🏛️' : '📍'}</Text>
            <Text style={styles.heroPlaceholderLabel}>No images yet</Text>
          </View>
        )}

        {/* Overlay gradient back button */}
        <TouchableOpacity
          onPress={() => router.back()}
          style={[styles.backBtn, { top: insets.top + scale(8) }]}
        >
          <Text style={styles.backBtnText}>←</Text>
        </TouchableOpacity>
      </View>

      {/* ── Spot Info Strip ── */}
      <View style={styles.infoStrip}>
        <Text style={styles.spotName} numberOfLines={2}>{displayName}</Text>
        <Text style={styles.spotType}>{spot?.type === 'landmark' ? '🏛️ Heritage Landmark' : '📍 Point of Interest'}</Text>
        {spot?.tags && spot.tags.length > 0 && (
          <View style={styles.tagRow}>
            {spot.tags.map(t => (
              <View key={t} style={styles.tag}><Text style={styles.tagText}>{t}</Text></View>
            ))}
          </View>
        )}
      </View>

      {/* ── Tabs ── */}
      <View style={styles.tabRow}>
        {(['overview', 'details', 'chat'] as TabType[]).map(tab => (
          <TouchableOpacity key={tab} style={[styles.tab, activeTab === tab && styles.tabActive]} onPress={() => setActiveTab(tab)}>
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === 'overview' ? '📖 Overview' : tab === 'details' ? '📚 Details' : '💬 Chat'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Overview Tab ── */}
      {activeTab === 'overview' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {spot?.description ? (
            <>
              <Text style={styles.sectionTitle}>About</Text>
              <Text style={styles.bodyText}>{spot.description}</Text>
            </>
          ) : null}
          {content?.overview ? (
            <>
              <Text style={styles.sectionTitle}>Overview</Text>
              <Text style={styles.bodyText}>{content.overview}</Text>
            </>
          ) : !spot?.description ? (
            <Text style={styles.mutedText}>No overview available yet. Check back after the admin publishes content for this spot.</Text>
          ) : null}
        </ScrollView>
      )}

      {/* ── Details Tab ── */}
      {activeTab === 'details' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {content?.history ? (
            <>
              <Text style={styles.sectionTitle}>History</Text>
              <Text style={styles.bodyText}>{content.history}</Text>
            </>
          ) : null}
          {content?.culture ? (
            <>
              <Text style={styles.sectionTitle}>Culture</Text>
              <Text style={styles.bodyText}>{content.culture}</Text>
            </>
          ) : null}
          {content?.funFacts ? (
            <>
              <Text style={styles.sectionTitle}>Fun Facts 🎉</Text>
              <Text style={styles.bodyText}>{content.funFacts}</Text>
            </>
          ) : null}
          {!content?.history && !content?.culture && !content?.funFacts && (
            <Text style={styles.mutedText}>No detailed content available yet.</Text>
          )}
        </ScrollView>
      )}

      {/* ── Chat Tab ── */}
      {activeTab === 'chat' && (
        <View style={{ flex: 1 }}>
          <FlatList
            data={chatMessages}
            keyExtractor={(_, i) => i.toString()}
            contentContainerStyle={{ padding: Spacing.md, paddingBottom: scale(80) }}
            renderItem={({ item, index }) => {
              const isUser = item.role === 'user';
              const prevUserMsg = chatMessages.slice(0, index).reverse().find(m => m.role === 'user')?.content;
              return (
                <View style={{ marginBottom: Spacing.sm }}>
                  <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
                    <Text style={[styles.bubbleText, isUser && { color: Colors.white }]}>{item.content}</Text>
                  </View>
                  {!isUser && (
                    <View style={styles.feedbackRow}>
                      {([1, -1] as const).map(r => {
                        const voted = ratedMessages[index];
                        const active = voted === r;
                        return (
                          <TouchableOpacity key={r} disabled={voted !== undefined}
                            onPress={() => {
                              if (r === 1) {
                                void sendChatFeedback(index, 1, item.content, prevUserMsg);
                              } else {
                                setPendingBadFeedback({ idx: index, aiMessage: item.content, userMessage: prevUserMsg });
                                setFeedbackModalVisible(true);
                              }
                            }}
                            style={[styles.feedbackBtn, active && styles.feedbackBtnActive]}>
                            <Text style={{ fontSize: scale(13) }}>{r === 1 ? '👍 Good' : '👎 Bad'}</Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  )}
                </View>
              );
            }}
          />
          <View style={styles.suggestRow}>
            {['Tell me the history', 'Fun facts please', 'How do I get there?'].map(q => (
              <TouchableOpacity key={q} style={styles.suggestBtn} onPress={() => setChatInput(q)}>
                <Text style={styles.suggestText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={[styles.chatBar, { paddingBottom: Spacing.sm + insets.bottom }]}>
            <TextInput
              style={styles.chatInput}
              placeholder="Ask about this place..."
              placeholderTextColor={Colors.textMuted}
              value={chatInput}
              onChangeText={setChatInput}
            />
            <TouchableOpacity style={styles.chatSend} onPress={handleChat} disabled={chatLoading}>
              <Text style={styles.chatSendText}>{chatLoading ? '...' : '↑'}</Text>
            </TouchableOpacity>
          </View>

          <Modal visible={feedbackModalVisible} transparent animationType="fade" onRequestClose={() => setFeedbackModalVisible(false)}>
            <View style={styles.modalOverlay}>
              <View style={styles.modalBox}>
                <Text style={styles.modalTitle}>What was bad about this answer? 👎</Text>
                <TextInput
                  style={styles.modalInput}
                  placeholder="Optional: tell us what should improve"
                  placeholderTextColor={Colors.textMuted}
                  value={feedbackComment}
                  onChangeText={setFeedbackComment}
                  multiline
                />
                <View style={styles.modalButtons}>
                  <TouchableOpacity style={styles.modalCancel} onPress={() => setFeedbackModalVisible(false)}>
                    <Text style={{ color: Colors.textSecondary }}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.modalSubmit} onPress={() => { void submitBadFeedback(); }}>
                    <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </Modal>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },

  // Hero
  heroContainer: { width: SCREEN_W, height: HERO_H, position: 'relative', backgroundColor: Colors.border },
  heroImage: { width: SCREEN_W, height: HERO_H },
  heroPlaceholder: { justifyContent: 'center', alignItems: 'center', backgroundColor: '#e8f0fe' },
  heroPlaceholderText: { fontSize: scale(56) },
  heroPlaceholderLabel: { fontSize: scale(12), color: Colors.textMuted, marginTop: scale(6) },
  dotsRow: { position: 'absolute', bottom: scale(10), flexDirection: 'row', width: '100%', justifyContent: 'center', gap: scale(5) },
  dot: { width: scale(6), height: scale(6), borderRadius: scale(3), backgroundColor: 'rgba(255,255,255,0.5)' },
  dotActive: { backgroundColor: Colors.white, width: scale(14) },
  backBtn: {
    position: 'absolute', left: scale(12),
    width: scale(36), height: scale(36), borderRadius: scale(18),
    backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center',
  },
  backBtnText: { fontSize: scale(18), color: Colors.white, fontWeight: '700' },

  // Info strip
  infoStrip: { backgroundColor: Colors.white, padding: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  spotName: { fontSize: scale(20), fontWeight: '800', color: Colors.textPrimary, marginBottom: scale(3) },
  spotType: { fontSize: scale(12), color: Colors.textMuted, marginBottom: scale(6) },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: scale(4) },
  tag: { backgroundColor: Colors.accentLight, borderRadius: Radius.full, paddingVertical: scale(3), paddingHorizontal: scale(8) },
  tagText: { fontSize: scale(10), color: Colors.accentDark, fontWeight: '600' },

  // Tabs
  tabRow: { flexDirection: 'row', backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tab: { flex: 1, paddingVertical: scale(10), alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: Colors.accent },
  tabText: { fontSize: scale(11), fontWeight: '600', color: Colors.textMuted },
  tabTextActive: { color: Colors.accent },
  tabContent: { padding: Spacing.md, paddingBottom: scale(40) },

  // Content
  sectionTitle: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm, marginTop: Spacing.md },
  bodyText: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(21) },
  mutedText: { fontSize: scale(13), color: Colors.textMuted, textAlign: 'center', marginTop: scale(40), lineHeight: scale(20) },

  // Chat
  bubble: { padding: scale(10), borderRadius: Radius.lg, marginBottom: Spacing.sm, maxWidth: '85%' },
  aiBubble: { backgroundColor: Colors.white, alignSelf: 'flex-start', borderBottomLeftRadius: scale(4) },
  userBubble: { backgroundColor: Colors.primary, alignSelf: 'flex-end', borderBottomRightRadius: scale(4) },
  bubbleText: { fontSize: scale(13), color: Colors.textPrimary, lineHeight: scale(19) },
  suggestRow: { flexDirection: 'row', paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs, flexWrap: 'wrap' },
  suggestBtn: { backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(10) },
  suggestText: { fontSize: scale(10), color: Colors.textPrimary, fontWeight: '500' },
  chatBar: {
    flexDirection: 'row', padding: Spacing.sm, backgroundColor: Colors.white,
    borderTopWidth: 1, borderTopColor: Colors.border, gap: Spacing.sm,
  },
  chatInput: {
    flex: 1, backgroundColor: Colors.inputBg, borderRadius: Radius.full,
    paddingHorizontal: Spacing.md, paddingVertical: scale(8),
    fontSize: scale(13), color: Colors.textPrimary,
  },
  chatSend: { width: scale(36), height: scale(36), borderRadius: scale(18), backgroundColor: Colors.accent, justifyContent: 'center', alignItems: 'center' },
  chatSendText: { color: Colors.white, fontSize: scale(16), fontWeight: '700' },
  feedbackRow: { flexDirection: 'row', gap: scale(6), marginTop: scale(3), paddingLeft: scale(4) },
  feedbackBtn: { paddingHorizontal: scale(8), paddingVertical: scale(3), borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.white },
  feedbackBtnActive: { backgroundColor: Colors.accentLight, borderColor: Colors.accent },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalBox: { backgroundColor: Colors.white, borderTopLeftRadius: Radius.xl, borderTopRightRadius: Radius.xl, padding: Spacing.lg, paddingBottom: scale(36) },
  modalTitle: { fontSize: scale(16), fontWeight: '800', color: Colors.textPrimary, marginBottom: Spacing.md },
  modalInput: { backgroundColor: Colors.inputBg, borderRadius: Radius.md, padding: Spacing.sm, fontSize: scale(13), color: Colors.textPrimary, minHeight: scale(60), textAlignVertical: 'top', marginBottom: Spacing.md },
  modalButtons: { flexDirection: 'row', gap: Spacing.sm },
  modalCancel: { flex: 1, padding: Spacing.sm, borderRadius: Radius.md, borderWidth: 1, borderColor: Colors.border, alignItems: 'center' },
  modalSubmit: { flex: 1, padding: Spacing.sm, borderRadius: Radius.md, backgroundColor: '#7c3aed', alignItems: 'center' },
});
