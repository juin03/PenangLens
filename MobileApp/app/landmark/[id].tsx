import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, FlatList, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL, chatWithAgent } from '@/api/client';

type TabType = 'overview' | 'details' | 'chat';
interface ChatMsg { role: 'user' | 'assistant'; content: string; }

interface SpotDetail {
  id: string;
  name: string;
  type: string;
  description?: string;
  content?: { overview?: string; history?: string; culture?: string; funFacts?: string };
  tags?: string[];
  lat?: number;
  lng?: number;
}

export default function SpotDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const spotId = typeof params.id === 'string' ? params.id : '';
  const nameParam = typeof params.name === 'string' ? params.name : 'Landmark';

  const [spot, setSpot] = useState<SpotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: `Hi! Ask me anything about ${nameParam}.` },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);

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

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Text style={styles.headerBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{displayName}</Text>
        <View style={styles.headerBtn} />
      </View>

      {/* Hero badge */}
      {!loading && (
        <View style={styles.heroCard}>
          <View style={styles.heroIcon}>
            <Text style={styles.heroIconText}>{spot?.type === 'landmark' ? '🏛️' : '📍'}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.heroName}>{displayName}</Text>
            <Text style={styles.heroType}>{spot?.type === 'landmark' ? 'Heritage Landmark' : 'Point of Interest'}</Text>
            {spot?.tags && spot.tags.length > 0 && (
              <View style={styles.tagRow}>
                {spot.tags.map(t => (
                  <View key={t} style={styles.tag}><Text style={styles.tagText}>{t}</Text></View>
                ))}
              </View>
            )}
          </View>
        </View>
      )}

      {/* Tabs */}
      <View style={styles.tabRow}>
        {(['overview', 'details', 'chat'] as TabType[]).map(tab => (
          <TouchableOpacity key={tab} style={[styles.tab, activeTab === tab && styles.tabActive]} onPress={() => setActiveTab(tab)}>
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Overview Tab ── */}
      {activeTab === 'overview' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {loading ? (
            <ActivityIndicator color={Colors.accent} style={{ marginTop: scale(30) }} />
          ) : (
            <>
              <Text style={styles.sectionTitle}>About</Text>
              <Text style={styles.bodyText}>
                {content?.overview || spot?.description || 'No overview available yet. Check back after the admin publishes content for this spot.'}
              </Text>
            </>
          )}
        </ScrollView>
      )}

      {/* ── Details Tab ── */}
      {activeTab === 'details' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {loading ? (
            <ActivityIndicator color={Colors.accent} style={{ marginTop: scale(30) }} />
          ) : (
            <>
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
                  <Text style={styles.sectionTitle}>Fun Facts</Text>
                  <Text style={styles.bodyText}>{content.funFacts}</Text>
                </>
              ) : null}
              {!content?.history && !content?.culture && !content?.funFacts && (
                <Text style={styles.mutedText}>No detailed content available yet.</Text>
              )}
            </>
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
            renderItem={({ item }) => (
              <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.aiBubble]}>
                <Text style={[styles.bubbleText, item.role === 'user' && { color: Colors.white }]}>{item.content}</Text>
              </View>
            )}
          />
          <View style={styles.suggestRow}>
            {['Tell me the history', 'Fun facts please', 'How do I get there?'].map(q => (
              <TouchableOpacity key={q} style={styles.suggestBtn} onPress={() => setChatInput(q)}>
                <Text style={styles.suggestText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.chatBar}>
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
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: Colors.white, paddingTop: scale(48), paddingBottom: scale(10),
    paddingHorizontal: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  headerBtn: { width: scale(32), height: scale(32), borderRadius: scale(16), justifyContent: 'center', alignItems: 'center' },
  headerBtnText: { fontSize: scale(18), color: Colors.textPrimary, fontWeight: '600' },
  headerTitle: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary, flex: 1, textAlign: 'center' },
  heroCard: {
    flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.md,
    backgroundColor: Colors.white, padding: Spacing.md,
    borderBottomWidth: 1, borderBottomColor: Colors.border,
  },
  heroIcon: {
    width: scale(52), height: scale(52), borderRadius: Radius.md,
    backgroundColor: Colors.primaryLight, justifyContent: 'center', alignItems: 'center',
  },
  heroIconText: { fontSize: scale(26) },
  heroName: { fontSize: scale(16), fontWeight: '800', color: Colors.textPrimary },
  heroType: { fontSize: scale(11), color: Colors.textMuted, marginTop: scale(2), marginBottom: scale(6) },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: scale(4) },
  tag: { backgroundColor: Colors.accentLight, borderRadius: Radius.full, paddingVertical: scale(3), paddingHorizontal: scale(8) },
  tagText: { fontSize: scale(10), color: Colors.accentDark, fontWeight: '600' },
  tabRow: { flexDirection: 'row', backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tab: { flex: 1, paddingVertical: scale(10), alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: Colors.accent },
  tabText: { fontSize: scale(12), fontWeight: '600', color: Colors.textMuted },
  tabTextActive: { color: Colors.accent },
  tabContent: { padding: Spacing.md },
  sectionTitle: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  bodyText: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(20) },
  mutedText: { fontSize: scale(13), color: Colors.textMuted, textAlign: 'center', marginTop: scale(30) },
  bubble: { padding: scale(10), borderRadius: Radius.lg, marginBottom: Spacing.sm, maxWidth: '85%' },
  aiBubble: { backgroundColor: Colors.white, alignSelf: 'flex-start', borderBottomLeftRadius: scale(4) },
  userBubble: { backgroundColor: Colors.primary, alignSelf: 'flex-end', borderBottomRightRadius: scale(4) },
  bubbleText: { fontSize: scale(13), color: Colors.textPrimary, lineHeight: scale(19) },
  suggestRow: { flexDirection: 'row', paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
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
});
