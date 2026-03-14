import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, TextInput, FlatList, Image, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL, saveScanResult, chatWithAgent } from '@/api/client';

type TabType = 'result' | 'details' | 'chat';
interface ChatMsg { role: 'user' | 'assistant'; content: string; }
interface SpotData { id: string; name: string; type: string; description?: string; tags?: string[]; lat?: number; lng?: number; parentLandmark?: string; }

/** Fetch all published spots from the BFF and return the one matching spotId */
async function fetchSpotById(spotId: string): Promise<SpotData | null> {
  try {
    const BASE = API_BASE_URL.replace('/api/v1', '');
    const res = await fetch(`${BASE}/api/spots/map`);
    if (!res.ok) return null;
    const data = await res.json();
    const spots: SpotData[] = data.spots || [];
    return spots.find(s => s.id === spotId) ?? null;
  } catch {
    return null;
  }
}

/** Pick a few nearby spots to show as suggestions (excludes current spot) */
function pickNearby(spots: SpotData[], currentId: string, max = 3): SpotData[] {
  return spots.filter(s => s.id !== currentId).slice(0, max);
}

export default function LandmarkResultScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const [activeTab, setActiveTab] = useState<TabType>('result');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: "Hi! I'm your guide. What would you like to know about this landmark?" },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);

  const [nearbySpots, setNearbySpots] = useState<SpotData[]>([]);
  const [spotContent, setSpotContent] = useState<{overview?: string; history?: string; culture?: string; funFacts?: string} | null>(null);
  const [spotLoading, setSpotLoading] = useState(false);

  // ── Parse incoming data ───────────────────────────────────
  let scanData: any = null;
  try { if (params.data && typeof params.data === 'string') scanData = JSON.parse(params.data); } catch {}

  const spotId = typeof params.spotId === 'string' ? params.spotId : scanData?.poi_id ?? null;
  const topDetection = scanData?.detections?.[0];
  const landmarkName = (typeof params.name === 'string' && params.name)
    ? params.name
    : scanData?.poi_name || topDetection?.class || 'Unknown Landmark';
  const confidence = topDetection ? Math.round(topDetection.confidence * 100) : 0;
  const annotatedImage = scanData?.image_url;
  const isScanResult = Boolean(scanData);

  // ── Load spot info from DB ───────────────────────────────
  useEffect(() => {
    if (!spotId) return;
    setSpotLoading(true);
    (async () => {
      try {
        const BASE = API_BASE_URL.replace('/api/v1', '');
        // Fetch all spots for nearby list
        const res = await fetch(`${BASE}/api/spots/map`);
        if (res.ok) {
          const data = await res.json();
          const spots: SpotData[] = data.spots || [];
          setNearbySpots(pickNearby(spots, spotId));
        }
        // Fetch single spot for content
        const spotRes = await fetch(`${BASE}/api/admin/spots/${spotId}`);
        if (spotRes.ok) {
          const spotData = await spotRes.json();
          const content = spotData.spot?.content;
          if (content && typeof content === 'object') setSpotContent(content);
        }
      } catch (e) {
        console.warn('Could not load spot detail:', e);
      } finally {
        setSpotLoading(false);
      }
    })();
  }, [spotId]);

  // ── Save scan to DB (fire-and-forget) ────────────────────
  useEffect(() => {
    if (!isScanResult || !scanData) return;
    saveScanResult({
      poiId: scanData.poi_id ?? undefined,
      aiDetails: { poi_name: scanData.poi_name, detections: scanData.detections, model: scanData.model },
    }).catch(() => {}); // silent — don't break UX
  }, []);

  // ── No data guard ────────────────────────────────────────
  if (!scanData && !spotId) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>No landmark data found.</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => router.back()}>
          <Text style={styles.retryText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── Agent chat ───────────────────────────────────────────
  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    try {
      const contextMsg = spotId
        ? `[Landmark context: ${landmarkName}] ${userMsg}`
        : userMsg;
      const data = await chatWithAgent({
        message: contextMsg,
        thread_id: threadId ?? `landmark_${(spotId || landmarkName).replace(/\s+/g, '_')}`,
      });
      setThreadId(data.thread_id);
      setChatMessages(prev => [...prev, { role: 'assistant', content: data.response || 'Sorry, I could not answer that.' }]);
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: 'Connection error. Please try again.' }]);
    } finally { setChatLoading(false); }
  };

  const overviewText = spotContent?.overview
    || scanData?.description
    || 'A notable landmark in Penang, Malaysia. Use the Chat tab to learn more about its history, architecture, and cultural significance.';

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Text style={styles.headerBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{landmarkName}</Text>
        <View style={styles.headerBtn} />
      </View>

      {/* Tabs */}
      <View style={styles.tabRow}>
        {(['result', 'details', 'chat'] as TabType[]).map(tab => (
          <TouchableOpacity key={tab} style={[styles.tab, activeTab === tab && styles.tabActive]} onPress={() => setActiveTab(tab)}>
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Result Tab ── */}
      {activeTab === 'result' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {annotatedImage && (
            <Image source={{ uri: annotatedImage }} style={styles.annotatedImage} resizeMode="contain" />
          )}
          <View style={styles.resultCard}>
            <View style={styles.landmarkBadge}><Text style={styles.landmarkBadgeIcon}>🏛️</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.landmarkName}>{landmarkName}</Text>
              {isScanResult && confidence > 0 && (
                <Text style={styles.confText}>{confidence}% Match Confidence</Text>
              )}
            </View>
          </View>

          <Text style={styles.sectionTitle}>About</Text>
          {spotLoading ? (
            <ActivityIndicator color={Colors.accent} style={{ marginVertical: scale(10) }} />
          ) : (
            <Text style={styles.descText}>{overviewText}</Text>
          )}

          {nearbySpots.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Nearby Spots</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {nearbySpots.map(s => (
                  <TouchableOpacity
                    key={s.id}
                    style={styles.similarCard}
                    onPress={() => router.push({ pathname: '/landmark/[id]', params: { id: s.id, name: s.name } })}
                  >
                    <Text style={styles.similarIcon}>{s.type === 'landmark' ? '🏛️' : '📍'}</Text>
                    <Text style={styles.similarName} numberOfLines={2}>{s.name}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </>
          )}
        </ScrollView>
      )}

      {/* ── Details Tab ── */}
      {activeTab === 'details' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {annotatedImage && (
            <Image source={{ uri: annotatedImage }} style={styles.annotatedImage} resizeMode="contain" />
          )}

          {/* Content sections from DB */}
          {spotContent?.history && (
            <>
              <Text style={styles.sectionTitle}>History</Text>
              <Text style={styles.descText}>{spotContent.history}</Text>
            </>
          )}
          {spotContent?.culture && (
            <>
              <Text style={styles.sectionTitle}>Culture</Text>
              <Text style={styles.descText}>{spotContent.culture}</Text>
            </>
          )}
          {spotContent?.funFacts && (
            <>
              <Text style={styles.sectionTitle}>Fun Facts</Text>
              <Text style={styles.descText}>{spotContent.funFacts}</Text>
            </>
          )}

          {/* YOLO detections (only present on scan result) */}
          {scanData?.detections && scanData.detections.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Detected Details</Text>
              {scanData.detections.map((det: any, i: number) => (
                <TouchableOpacity key={i} style={styles.detailItem}>
                  <View style={[styles.detailDot, { backgroundColor: i === 0 ? Colors.accent : Colors.primaryLight }]} />
                  <Text style={styles.detailText}>{det.class}</Text>
                  <Text style={styles.detailConf}>{Math.round(det.confidence * 100)}%</Text>
                  <Text style={styles.detailArrow}>›</Text>
                </TouchableOpacity>
              ))}
            </>
          )}

          {!spotContent && (!scanData?.detections || scanData.detections.length === 0) && (
            <Text style={styles.noDetails}>No additional details available.</Text>
          )}
        </ScrollView>
      )}

      {/* ── Chat Tab ── */}
      {activeTab === 'chat' && (
        <View style={{ flex: 1 }}>
          <FlatList
            data={chatMessages}
            keyExtractor={(_, i) => i.toString()}
            contentContainerStyle={{ padding: Spacing.md, paddingBottom: scale(70) }}
            renderItem={({ item }) => (
              <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.aiBubble]}>
                <Text style={[styles.bubbleText, item.role === 'user' && { color: Colors.white }]}>{item.content}</Text>
              </View>
            )}
          />
          {/* Quick suggestions */}
          <View style={styles.suggestRow}>
            {['Who built this?', 'Tell me a fun fact', 'Why is it famous?'].map(q => (
              <TouchableOpacity key={q} style={styles.suggestBtn} onPress={() => setChatInput(q)}>
                <Text style={styles.suggestText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.chatBar}>
            <TextInput style={styles.chatInput} placeholder="Ask something else..." placeholderTextColor={Colors.textMuted} value={chatInput} onChangeText={setChatInput} />
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
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.lg },
  errorText: { fontSize: scale(16), color: Colors.error, marginBottom: Spacing.md },
  retryBtn: { backgroundColor: Colors.primary, borderRadius: Radius.md, paddingVertical: scale(10), paddingHorizontal: Spacing.lg },
  retryText: { color: Colors.white, fontWeight: '700' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.white, paddingTop: scale(48), paddingBottom: scale(10), paddingHorizontal: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  headerBtn: { width: scale(32), height: scale(32), borderRadius: scale(16), justifyContent: 'center', alignItems: 'center' },
  headerBtnText: { fontSize: scale(18), color: Colors.textPrimary, fontWeight: '600' },
  headerTitle: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary, flex: 1, textAlign: 'center' },
  tabRow: { flexDirection: 'row', backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tab: { flex: 1, paddingVertical: scale(10), alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: Colors.accent },
  tabText: { fontSize: scale(12), fontWeight: '600', color: Colors.textMuted },
  tabTextActive: { color: Colors.accent },
  tabContent: { padding: Spacing.md },
  annotatedImage: { width: '100%', height: scale(180), borderRadius: Radius.lg, marginBottom: Spacing.md, backgroundColor: Colors.inputBg },
  resultCard: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.md, backgroundColor: Colors.white, padding: Spacing.md, borderRadius: Radius.lg },
  landmarkBadge: { width: scale(44), height: scale(44), borderRadius: Radius.md, backgroundColor: Colors.primaryLight, justifyContent: 'center', alignItems: 'center' },
  landmarkBadgeIcon: { fontSize: scale(22) },
  landmarkName: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary },
  confText: { fontSize: scale(12), color: Colors.success, fontWeight: '600', marginTop: scale(2) },
  sectionTitle: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  descText: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(19) },
  similarCard: { backgroundColor: Colors.white, borderRadius: Radius.md, padding: scale(10), marginRight: Spacing.sm, alignItems: 'center', width: scale(90) },
  similarIcon: { fontSize: scale(22), marginBottom: scale(4) },
  similarName: { fontSize: scale(10), fontWeight: '600', color: Colors.textPrimary, textAlign: 'center' },
  detailItem: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, backgroundColor: Colors.white, padding: Spacing.md, borderRadius: Radius.md, marginBottom: Spacing.xs },
  detailDot: { width: scale(8), height: scale(8), borderRadius: scale(4) },
  detailText: { flex: 1, fontSize: scale(13), color: Colors.textPrimary, fontWeight: '500' },
  detailConf: { fontSize: scale(11), color: Colors.textMuted },
  detailArrow: { fontSize: scale(16), color: Colors.textMuted },
  noDetails: { fontSize: scale(13), color: Colors.textMuted, textAlign: 'center', marginTop: Spacing.lg },
  bubble: { padding: scale(10), borderRadius: Radius.lg, marginBottom: Spacing.sm, maxWidth: '85%' },
  aiBubble: { backgroundColor: Colors.white, alignSelf: 'flex-start', borderBottomLeftRadius: scale(4) },
  userBubble: { backgroundColor: Colors.primary, alignSelf: 'flex-end', borderBottomRightRadius: scale(4) },
  bubbleText: { fontSize: scale(13), color: Colors.textPrimary, lineHeight: scale(19) },
  suggestRow: { flexDirection: 'row', paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs },
  suggestBtn: { backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(10) },
  suggestText: { fontSize: scale(10), color: Colors.textPrimary, fontWeight: '500' },
  chatBar: { flexDirection: 'row', padding: Spacing.sm, backgroundColor: Colors.white, borderTopWidth: 1, borderTopColor: Colors.border, gap: Spacing.sm },
  chatInput: { flex: 1, backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingHorizontal: Spacing.md, paddingVertical: scale(8), fontSize: scale(13), color: Colors.textPrimary },
  chatSend: { width: scale(36), height: scale(36), borderRadius: scale(18), backgroundColor: Colors.accent, justifyContent: 'center', alignItems: 'center' },
  chatSendText: { color: Colors.white, fontSize: scale(16), fontWeight: '700' },
});
