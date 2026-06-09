import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, FlatList, Image, ActivityIndicator, Modal, Pressable,
  useWindowDimensions, Animated,
} from 'react-native';
import { useLocalSearchParams, useRouter, useNavigation } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { API_BASE_URL, saveScanResult, getToken } from '@/api/client';
import { streamChat } from '@/api/streaming';
import { MarkdownText } from '@/components/MarkdownText';
import CLASS_INFO from '@/constants/classDescriptions';

type TabType = 'result' | 'details' | 'chat';
interface ChatMsg { role: 'user' | 'assistant'; content: string; }
interface SpotData { id: string; name: string; type: string; description?: string; tags?: string[]; }

// Colour palette matching VisionML PALETTE (RGB hex)
const PALETTE = [
  '#FF6347','#1E90FF','#32CD32','#FFD700','#BA55D3','#FFA500',
  '#00CED1','#FF1493','#7FFF00','#FF4500','#6495ED','#90EE90',
  '#FFB6C1','#ADD8E6','#F0E68C','#DDA0DD','#98FB98','#87CEEB',
  '#FFA07A','#B0C4DE','#FFE4B5','#90EE90','#AFEEEE','#FFDEAD',
  '#D8BFD8','#F5F5DC','#E6E6FA','#FFF0F5','#F0FFF0','#FFFACD',
];

async function fetchSpotById(spotId: string): Promise<SpotData | null> {
  try {
    const BASE = API_BASE_URL.replace('/api/v1', '');
    const res = await fetch(`${BASE}/api/spots/map`);
    if (!res.ok) return null;
    const data = await res.json();
    const spots: SpotData[] = data.spots || [];
    return spots.find(s => s.id === spotId) ?? null;
  } catch { return null; }
}

function pickNearby(spots: SpotData[], currentId: string, max = 3): SpotData[] {
  return spots.filter(s => s.id !== currentId).slice(0, max);
}

// ── Expandable detection card ────────────────────────────────────────────────
function DetectionCard({ det, colorHex }: { det: any; colorHex: string }) {
  const [open, setOpen] = useState(false);
  // Normalise class key: lowercase + underscores
  const classKey = det.class.toLowerCase().replace(/\s+/g, '_');
  const info = CLASS_INFO[classKey];

  return (
    <Pressable onPress={() => setOpen(o => !o)} style={[styles.detCard, { borderLeftColor: colorHex }]}>
      <View style={styles.detCardHeader}>
        <View style={[styles.detDot, { backgroundColor: colorHex }]} />
        <Text style={styles.detLabel}>{info?.label ?? det.class.replace(/_/g, ' ')}</Text>
        <Text style={styles.detConf}>{Math.round(det.confidence * 100)}%</Text>
        <Text style={styles.detChevron}>{open ? '▾' : '›'}</Text>
      </View>
      {open && (
        <View style={styles.detBody}>
          {info ? (
            <>
              <Text style={styles.detDesc}>{info.description}</Text>
              <View style={styles.detSigBox}>
                <Text style={styles.detSigLabel}>✨ Significance</Text>
                <Text style={styles.detSig}>{info.significance}</Text>
              </View>
            </>
          ) : (
            <Text style={styles.detDesc}>No description available for this feature yet.</Text>
          )}
        </View>
      )}
    </Pressable>
  );
}

// ── Fullscreen viewer with class chips + zoom-to-bbox ───────────────────────
function FullscreenViewer({ imageUri, detections, onClose }: {
  imageUri: string;
  detections: any[];
  onClose: () => void;
}) {
  const { width: screenW, height: screenH } = useWindowDimensions();
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const translateX = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(1)).current;

  // Image is rendered at screenW × screenH*0.75 with contain
  const imgDisplayW = screenW;
  const imgDisplayH = screenH * 0.72;

  const zoomToDet = (det: any, idx: number) => {
    if (selectedIdx === idx) {
      // Deselect — reset
      setSelectedIdx(null);
      Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
      Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
      Animated.spring(translateY, { toValue: 0, useNativeDriver: true }).start();
      return;
    }
    setSelectedIdx(idx);
    const b = det.bbox;
    if (!b) return;

    // Centre of bbox in display coords
    const cx = ((b.x1 + b.x2) / 2) * imgDisplayW;
    const cy = ((b.y1 + b.y2) / 2) * imgDisplayH;
    const zoomScale = 2.5;

    // Translate so bbox centre moves to screen centre
    const tx = (screenW / 2 - cx) * (zoomScale - 1) / zoomScale;
    const ty = (imgDisplayH / 2 - cy) * (zoomScale - 1) / zoomScale;

    Animated.spring(scale, { toValue: zoomScale, useNativeDriver: true }).start();
    Animated.spring(translateX, { toValue: tx, useNativeDriver: true }).start();
    Animated.spring(translateY, { toValue: ty, useNativeDriver: true }).start();
  };

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={fs.container}>
        {/* Close */}
        <TouchableOpacity style={fs.closeBtn} onPress={onClose}>
          <Text style={fs.closeText}>✕</Text>
        </TouchableOpacity>

        {/* Zoomable image */}
        <Pressable style={fs.imageArea} onPress={() => {
          if (selectedIdx !== null) {
            setSelectedIdx(null);
            Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
            Animated.spring(translateX, { toValue: 0, useNativeDriver: true }).start();
            Animated.spring(translateY, { toValue: 0, useNativeDriver: true }).start();
          }
        }}>
          <Animated.Image
            source={{ uri: imageUri }}
            style={[fs.image, { width: imgDisplayW, height: imgDisplayH, transform: [{ scale }, { translateX }, { translateY }] }]}
            resizeMode="contain"
          />
        </Pressable>

        {/* Class chips */}
        <View style={fs.chipsWrap}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={fs.chips}>
            {detections.map((det, i) => {
              const color = PALETTE[det.color_idx ?? i % PALETTE.length];
              const label = CLASS_INFO[det.class.toLowerCase().replace(/\s+/g, '_')]?.label ?? det.class.replace(/_/g, ' ');
              const active = selectedIdx === i;
              return (
                <Pressable key={det.class} onPress={() => zoomToDet(det, i)}
                  style={[fs.chip, { borderColor: color, backgroundColor: active ? color : 'rgba(0,0,0,0.6)' }]}>
                  <View style={[fs.chipDot, { backgroundColor: color }]} />
                  <Text style={[fs.chipText, active && { color: '#000' }]} numberOfLines={1}>{label}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <Text style={fs.hint}>Tap a class to zoom · tap again to reset</Text>
        </View>
      </View>
    </Modal>
  );
}

const fs = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000', justifyContent: 'space-between' },
  closeBtn: { position: 'absolute', top: scale(48), right: scale(16), zIndex: 10, backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: scale(20), width: scale(36), height: scale(36), justifyContent: 'center', alignItems: 'center' },
  closeText: { color: '#fff', fontSize: scale(16), fontWeight: '700' },
  imageArea: { flex: 1, justifyContent: 'center', alignItems: 'center', overflow: 'hidden' },
  image: {},
  chipsWrap: { paddingBottom: scale(32), paddingTop: scale(8), backgroundColor: 'rgba(0,0,0,0.85)' },
  chips: { paddingHorizontal: scale(12), gap: scale(8), paddingBottom: scale(4) },
  chip: { flexDirection: 'row', alignItems: 'center', gap: scale(5), borderWidth: 1.5, borderRadius: scale(20), paddingVertical: scale(5), paddingHorizontal: scale(10) },
  chipDot: { width: scale(8), height: scale(8), borderRadius: scale(4) },
  chipText: { fontSize: scale(11), color: '#fff', fontWeight: '600', maxWidth: scale(100) },
  hint: { textAlign: 'center', color: 'rgba(255,255,255,0.4)', fontSize: scale(10), marginTop: scale(4) },
});

// ── Main screen ──────────────────────────────────────────────────────────────
export default function LandmarkResultScreen() {
  const router = useRouter();
  const navigation = useNavigation();
  const params = useLocalSearchParams();
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<TabType>('result');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: "Hi! I'm your Penang heritage guide. Ask me anything about this landmark — its history, architecture, or cultural significance." },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  // Per-session chat feedback (1–5 stars), prompted when leaving the chat
  const [chatRated, setChatRated] = useState(false);
  const [chatRatingModalVisible, setChatRatingModalVisible] = useState(false);
  const [chatStars, setChatStars] = useState(0);
  const [chatComment, setChatComment] = useState('');
  const userMsgCount = chatMessages.filter(m => m.role === 'user').length;
  const hasChatted = userMsgCount > 0;
  const [scanRecordId, setScanRecordId] = useState<string | null>(null);
  const [scanFeedbackSubmitted, setScanFeedbackSubmitted] = useState(false);
  const [scanFeedbackModalVisible, setScanFeedbackModalVisible] = useState(false);
  const [scanFeedbackComment, setScanFeedbackComment] = useState('');
  const [nearbySpots, setNearbySpots] = useState<SpotData[]>([]);
  const [spotContent, setSpotContent] = useState<{ overview?: string; history?: string; culture?: string; funFacts?: string } | null>(null);
  const [spotLoading, setSpotLoading] = useState(false);
  const [imageFullscreen, setImageFullscreen] = useState(false);

  // ── Parse incoming data ──────────────────────────────────────────────────
  let scanData: any = null;
  try { if (params.data && typeof params.data === 'string') scanData = JSON.parse(params.data); } catch {}

  const spotId = typeof params.spotId === 'string' ? params.spotId : scanData?.poi_id ?? null;
  const landmarkName = (typeof params.name === 'string' && params.name)
    ? params.name
    : scanData?.poi_name || scanData?.detections?.[0]?.class || 'Unknown Landmark';
  const parentLandmark: string | null = scanData?.parent_landmark ?? null;
  const annotatedImage = scanData?.image_url;
  const isScanResult = Boolean(scanData);
  const poiConfidence = scanData?.poi_confidence ? Math.round(scanData.poi_confidence * 100) : 0;

  // Deduplicate detections by class (keep highest confidence per class)
  const rawDetections: any[] = scanData?.detections ?? [];
  const uniqueDetections: any[] = Object.values(
    rawDetections.reduce((acc: any, det: any) => {
      const key = det.class.toLowerCase().replace(/\s+/g, '_');
      if (!acc[key] || det.confidence > acc[key].confidence) acc[key] = det;
      return acc;
    }, {})
  );

  // ── Load spot info ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!spotId) return;
    setSpotLoading(true);
    (async () => {
      try {
        const BASE = API_BASE_URL.replace('/api/v1', '');
        const res = await fetch(`${BASE}/api/spots/map`);
        if (res.ok) {
          const data = await res.json();
          setNearbySpots(pickNearby(data.spots || [], spotId));
        }
        const spotRes = await fetch(`${BASE}/api/admin/spots/${spotId}`);
        if (spotRes.ok) {
          const sd = await spotRes.json();
          if (sd.spot?.content && typeof sd.spot.content === 'object') setSpotContent(sd.spot.content);
        }
      } catch {}
      finally { setSpotLoading(false); }
    })();
  }, [spotId]);

  // ── Save scan ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isScanResult || !scanData) return;
    console.log('[SCAN] Saving scan result...');
    saveScanResult({
      poiId: scanData.poi_id ?? undefined,
      annotatedImageBase64: scanData.image_url ?? undefined,
      aiDetails: { poi_name: scanData.poi_name, detections: scanData.detections, model: scanData.model, timing_ms: scanData.timing_ms },
    })
      .then(d => { 
        console.log('[SCAN] Saved:', d?.scan?.id);
        if (d?.scan?.id) setScanRecordId(d.scan.id); 
      })
      .catch((e) => {
        console.warn('[SCAN] Failed with image, retrying without:', e.message);
        saveScanResult({
          poiId: scanData.poi_id ?? undefined,
          aiDetails: { poi_name: scanData.poi_name, detections: scanData.detections, model: scanData.model, timing_ms: scanData.timing_ms },
        })
          .then(d => { 
            console.log('[SCAN] Saved without image:', d?.scan?.id);
            if (d?.scan?.id) setScanRecordId(d.scan.id); 
          })
          .catch((e2) => console.error('[SCAN] Both attempts failed:', e2.message));
      });
  }, []);

  // ── Prompt for a session chat rating when leaving (only if the user chatted) ──
  const pendingLeaveAction = useRef<any>(null);
  useEffect(() => {
    const unsub = (navigation as any).addListener('beforeRemove', (e: any) => {
      if (!hasChatted || chatRated) return; // nothing to rate, or already rated → leave freely
      e.preventDefault();                    // pause navigation
      pendingLeaveAction.current = e.data.action;
      setChatRatingModalVisible(true);       // ask for a rating
    });
    return unsub;
  }, [navigation, hasChatted, chatRated]);

  /** Close the rating modal. If it was opened by a navigation attempt, resume that
   *  navigation; if opened manually via the "Rate" button, just close it. */
  const closeRatingModal = () => {
    setChatRatingModalVisible(false);
    const action = pendingLeaveAction.current;
    pendingLeaveAction.current = null;
    if (action) (navigation as any).dispatch(action); // resume the leave the user attempted
  };

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

  // ── Feedback helpers ─────────────────────────────────────────────────────
  /** Submit a per-session 1–5 star rating for the whole conversation. */
  const submitChatRating = async (stars: number, comment?: string) => {
    setChatRated(true); // mark done immediately so the leave-prompt won't re-fire
    try {
      const BASE = API_BASE_URL.replace('/api/v1', '');
      const token = await getToken();
      await fetch(`${BASE}/api/v1/feedback/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          rating: stars,
          comment: comment || undefined,
          context: landmarkName,
          threadId,
          messageCount: userMsgCount,
        }),
      });
    } catch {}
  };

  const submitScanFeedback = async (verdict: 'good' | 'bad', comment?: string) => {
    if (!scanRecordId || scanFeedbackSubmitted) return;
    try {
      const BASE = API_BASE_URL.replace('/api/v1', '');
      const token = await getToken();
      const res = await fetch(`${BASE}/api/v1/feedback/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ recognitionId: scanRecordId, verdict, comment }),
      });
      if (res.ok) setScanFeedbackSubmitted(true);
    } catch {}
  };

  // ── Chat ─────────────────────────────────────────────────────────────────
  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setChatLoading(true);
    const aiMsgIndex = chatMessages.length + 1;
    setChatMessages(prev => [...prev, { role: 'assistant', content: '' }]);

    try {
      // Build class info for detected and all known classes
      const detectedClasses = uniqueDetections.map(d => ({
        class: d.class,
        confidence: d.confidence,
      }));
      // All classes for this landmark from CLASS_INFO keys that match detections' parent
      const allClassKeys = Object.keys(CLASS_INFO);

      const stream = streamChat(
        `[Landmark: ${landmarkName}] ${userMsg}`,
        threadId ?? `landmark_${(spotId || landmarkName).replace(/\s+/g, '_')}`,
        spotId,
        'landmark_chat',
        {
          detected_classes: detectedClasses,
          all_classes: allClassKeys,
        },
      );
      let fullResponse = '';
      for await (const update of stream) {
        if (update.type === 'chunk') {
          fullResponse += update.content;
          setChatMessages(prev => {
            const msgs = [...prev];
            msgs[aiMsgIndex] = { role: 'assistant', content: fullResponse };
            return msgs;
          });
        } else if (update.type === 'complete') {
          setThreadId(update.data?.thread_id);
        }
      }
    } catch {
      setChatMessages(prev => {
        const msgs = [...prev];
        msgs[aiMsgIndex] = { role: 'assistant', content: 'Connection error. Please try again.' };
        return msgs;
      });
    } finally { setChatLoading(false); }
  };

  const overviewText = spotContent?.overview
    || scanData?.description
    || (spotId ? 'A notable heritage landmark in Penang, Malaysia. Tap the Chat tab to explore its history, architecture, and cultural significance.' : null);

  // Determine which tabs to show
  const isUnknownLandmark = !spotId && landmarkName === 'Unknown Landmark';
  const hasDetections = uniqueDetections.length > 0;
  const availableTabs: TabType[] = isUnknownLandmark
    ? ['result']  // Unknown landmark: only result tab
    : hasDetections
      ? ['result', 'details', 'chat']  // Known + detections: all tabs
      : ['result', 'chat'];  // Known but no detections: no details tab

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + scale(8) }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Text style={styles.headerBtnText}>←</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{landmarkName}</Text>
        <View style={styles.headerBtn} />
      </View>

      {/* Tabs */}
      <View style={styles.tabRow}>
        {availableTabs.map(tab => (
          <TouchableOpacity key={tab} style={[styles.tab, activeTab === tab && styles.tabActive]} onPress={() => setActiveTab(tab)}>
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab === 'result' ? '🔍 Result' : tab === 'details' ? '📋 Details' : '💬 Chat'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Result Tab ── */}
      {activeTab === 'result' && (
        <ScrollView contentContainerStyle={styles.tabContent}>
          {/* Annotated image */}
          {annotatedImage && (
            <View style={styles.imageWrap}>
              <Pressable onPress={() => setImageFullscreen(true)}>
                <Image source={{ uri: annotatedImage }} style={styles.annotatedImage} resizeMode="cover" />
                <View style={styles.imageExpandHint}>
                  <Text style={styles.imageExpandText}>🔍 Tap to enlarge</Text>
                </View>
              </Pressable>
              {/* Colour legend */}
              {uniqueDetections.length > 0 && (
                <View style={styles.legend}>
                  {uniqueDetections.map((det, i) => (
                    <View key={det.class} style={styles.legendItem}>
                      <View style={[styles.legendDot, { backgroundColor: PALETTE[det.color_idx ?? i % PALETTE.length] }]} />
                      <Text style={styles.legendText} numberOfLines={1}>
                        {CLASS_INFO[det.class.toLowerCase().replace(/\s+/g, '_')]?.label ?? det.class.replace(/_/g, ' ')}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}

          {/* Landmark card */}
          <View style={styles.resultCard}>
            <View style={styles.landmarkBadge}><Text style={styles.landmarkBadgeIcon}>🏛️</Text></View>
            <View style={{ flex: 1 }}>
              {parentLandmark && (
                <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: scale(4) }}>
                  <Text style={{ fontSize: scale(11), color: Colors.accent, fontWeight: '600' }}>📍 {parentLandmark}</Text>
                </View>
              )}
              <Text style={styles.landmarkName}>{landmarkName}</Text>
              {isScanResult && poiConfidence > 0 && (
                <Text style={styles.confText}>
                  {poiConfidence >= 60 ? '✅' : '⚠️'} {poiConfidence}% landmark match · {uniqueDetections.length} feature{uniqueDetections.length !== 1 ? 's' : ''} detected
                </Text>
              )}
              {isScanResult && (
                <View style={{ marginTop: scale(8) }}>
                  {scanFeedbackSubmitted ? (
                    <Text style={styles.scanFeedbackThanks}>✅ Feedback submitted — thank you!</Text>
                  ) : (
                    <View style={styles.scanFeedbackRow}>
                      <TouchableOpacity style={styles.scanFeedbackBtn} onPress={() => void submitScanFeedback('good')}>
                        <Text style={styles.scanFeedbackBtnText}>👍 Correct</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={styles.scanFeedbackBtn} onPress={() => setScanFeedbackModalVisible(true)}>
                        <Text style={styles.scanFeedbackBtnText}>👎 Wrong</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              )}
            </View>
          </View>

          {/* About */}
          <Text style={styles.sectionTitle}>About</Text>
          {spotLoading
            ? <ActivityIndicator color={Colors.accent} style={{ marginVertical: scale(10) }} />
            : isUnknownLandmark
              ? <Text style={styles.descText}>This landmark was not recognized. Try scanning from a different angle or distance, or ensure the landmark is in our database.</Text>
              : <Text style={styles.descText}>{overviewText}</Text>
          }

          {/* History / Culture / Fun Facts */}
          {spotContent?.history && (
            <><Text style={styles.sectionTitle}>History</Text><Text style={styles.descText}>{spotContent.history}</Text></>
          )}
          {spotContent?.culture && (
            <><Text style={styles.sectionTitle}>Culture</Text><Text style={styles.descText}>{spotContent.culture}</Text></>
          )}
          {spotContent?.funFacts && (
            <><Text style={styles.sectionTitle}>Fun Facts 🎉</Text><Text style={styles.descText}>{spotContent.funFacts}</Text></>
          )}

          {/* Nearby */}
          {nearbySpots.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Nearby Spots</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {nearbySpots.map(s => (
                  <TouchableOpacity key={s.id} style={styles.similarCard}
                    onPress={() => router.push({ pathname: '/landmark/[id]', params: { id: s.id, name: s.name } })}>
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
            <View style={styles.imageWrap}>
              <Pressable onPress={() => setImageFullscreen(true)}>
                <Image source={{ uri: annotatedImage }} style={styles.annotatedImage} resizeMode="cover" />
                <View style={styles.imageExpandHint}>
                  <Text style={styles.imageExpandText}>🔍 Tap to enlarge</Text>
                </View>
              </Pressable>
              {uniqueDetections.length > 0 && (
                <View style={styles.legend}>
                  {uniqueDetections.map((det, i) => (
                    <View key={det.class} style={styles.legendItem}>
                      <View style={[styles.legendDot, { backgroundColor: PALETTE[det.color_idx ?? i % PALETTE.length] }]} />
                      <Text style={styles.legendText} numberOfLines={1}>
                        {CLASS_INFO[det.class.toLowerCase().replace(/\s+/g, '_')]?.label ?? det.class.replace(/_/g, ' ')}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}

          {uniqueDetections.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>
                Detected Architectural Features ({uniqueDetections.length})
              </Text>
              <Text style={styles.detHint}>Tap any feature to learn more</Text>
              {uniqueDetections.map((det, i) => (
                <DetectionCard
                  key={det.class}
                  det={det}
                  colorHex={PALETTE[det.color_idx ?? i % PALETTE.length]}
                />
              ))}
            </>
          )}

          {!spotContent && uniqueDetections.length === 0 && (
            <Text style={styles.noDetails}>No additional details available.</Text>
          )}
        </ScrollView>
      )}

      {/* ── Chat Tab ── */}
      {activeTab === 'chat' && (
        <View style={{ flex: 1 }}>
          {/* Context pill */}
          {uniqueDetections.length > 0 && (
            <View style={styles.contextPill}>
              <Text style={styles.contextPillText}>
                🧠 Context: {landmarkName} · {uniqueDetections.length} features detected
              </Text>
            </View>
          )}

          <FlatList
            data={chatMessages}
            keyExtractor={(_, i) => i.toString()}
            contentContainerStyle={{ padding: Spacing.md, paddingBottom: scale(80) }}
            renderItem={({ item }) => {
              const isUser = item.role === 'user';
              return (
                <View style={{ marginBottom: Spacing.sm }}>
                  <View style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
                    {isUser
                      ? <Text style={[styles.bubbleText, { color: Colors.white }]}>{item.content}</Text>
                      : <MarkdownText style={styles.bubbleText}>{item.content}</MarkdownText>
                    }
                  </View>
                </View>
              );
            }}
          />

          {/* Quick suggestions */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.suggestScroll} contentContainerStyle={styles.suggestContent}>
            {['Who built this?', 'Tell me a fun fact', 'Why is it famous?', 'What style of architecture?', 'Best time to visit?'].map(q => (
              <TouchableOpacity key={q} style={styles.suggestBtn} onPress={() => setChatInput(q)}>
                <Text style={styles.suggestText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {hasChatted && !chatRated && (
            <TouchableOpacity
              style={styles.rateSessionBtn}
              onPress={() => { setChatStars(0); setChatComment(''); setChatRatingModalVisible(true); }}
            >
              <Text style={styles.rateSessionText}>⭐ Rate this conversation</Text>
            </TouchableOpacity>
          )}
          {chatRated && (
            <View style={styles.rateSessionDone}>
              <Text style={styles.rateSessionDoneText}>✓ Thanks for your feedback!</Text>
            </View>
          )}

          <View style={[styles.chatBar, { paddingBottom: Spacing.sm + insets.bottom }]}>
            <TextInput
              style={styles.chatInput}
              placeholder="Ask about this landmark..."
              placeholderTextColor={Colors.textMuted}
              value={chatInput}
              onChangeText={setChatInput}
              onSubmitEditing={handleChat}
              returnKeyType="send"
            />
            <TouchableOpacity style={[styles.chatSend, chatLoading && { opacity: 0.5 }]} onPress={handleChat} disabled={chatLoading}>
              <Text style={styles.chatSendText}>{chatLoading ? '…' : '↑'}</Text>
            </TouchableOpacity>
          </View>

        </View>
      )}

      {/* Per-session chat rating modal — prompted when leaving after chatting */}
      <Modal visible={chatRatingModalVisible} transparent animationType="fade" onRequestClose={closeRatingModal}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>How was this conversation?</Text>
            <View style={{ flexDirection: 'row', justifyContent: 'center', gap: scale(6), marginVertical: scale(12) }}>
              {[1, 2, 3, 4, 5].map(star => (
                <TouchableOpacity key={star} onPress={() => setChatStars(star)}>
                  <Text style={{ fontSize: scale(30), color: star <= chatStars ? '#f59e0b' : Colors.border }}>
                    {star <= chatStars ? '★' : '☆'}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput style={styles.modalInput} placeholder="Optional comment..." placeholderTextColor={Colors.textMuted}
              value={chatComment} onChangeText={setChatComment} multiline />
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.modalCancel} onPress={closeRatingModal}>
                <Text style={{ color: Colors.textSecondary }}>Skip</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalSubmit, chatStars === 0 && { opacity: 0.5 }]}
                disabled={chatStars === 0}
                onPress={async () => {
                  await submitChatRating(chatStars, chatComment.trim() || undefined);
                  setChatComment(''); setChatStars(0);
                  closeRatingModal();
                }}>
                <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Scan feedback modal */}
      <Modal visible={scanFeedbackModalVisible} transparent animationType="fade" onRequestClose={() => setScanFeedbackModalVisible(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>What was wrong with this scan?</Text>
            <TextInput style={styles.modalInput} placeholder="Optional comment..." placeholderTextColor={Colors.textMuted}
              value={scanFeedbackComment} onChangeText={setScanFeedbackComment} multiline />
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.modalCancel} onPress={() => setScanFeedbackModalVisible(false)}>
                <Text style={{ color: Colors.textSecondary }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalSubmit} onPress={async () => {
                await submitScanFeedback('bad', scanFeedbackComment.trim() || undefined);
                setScanFeedbackComment(''); setScanFeedbackModalVisible(false);
              }}>
                <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Fullscreen image modal with class chips + zoom */}
      {imageFullscreen && (
        <FullscreenViewer
          imageUri={annotatedImage ?? ''}
          detections={uniqueDetections}
          onClose={() => setImageFullscreen(false)}
        />
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

  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: Colors.white, paddingBottom: scale(10), paddingHorizontal: Spacing.md, borderBottomWidth: 1, borderBottomColor: Colors.border },
  headerBtn: { width: scale(32), height: scale(32), borderRadius: scale(16), justifyContent: 'center', alignItems: 'center' },
  headerBtnText: { fontSize: scale(20), color: Colors.textPrimary, fontWeight: '600' },
  headerTitle: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary, flex: 1, textAlign: 'center' },

  tabRow: { flexDirection: 'row', backgroundColor: Colors.white, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tab: { flex: 1, paddingVertical: scale(10), alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: Colors.accent },
  tabText: { fontSize: scale(11), fontWeight: '600', color: Colors.textMuted },
  tabTextActive: { color: Colors.accent },
  tabContent: { padding: Spacing.md, paddingBottom: scale(40) },

  imageWrap: { borderRadius: Radius.lg, overflow: 'hidden', marginBottom: Spacing.md, backgroundColor: '#000' },
  annotatedImage: { width: '100%', height: scale(220) },
  imageExpandHint: { position: 'absolute', bottom: scale(8), right: scale(8), backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: Radius.sm, paddingHorizontal: scale(8), paddingVertical: scale(3) },
  imageExpandText: { fontSize: scale(10), color: '#fff', fontWeight: '600' },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: scale(6), padding: scale(8), backgroundColor: 'rgba(0,0,0,0.75)' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: scale(4) },
  legendDot: { width: scale(10), height: scale(10), borderRadius: scale(5) },
  legendText: { fontSize: scale(10), color: '#fff', fontWeight: '600', maxWidth: scale(90) },

  resultCard: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.md, backgroundColor: Colors.white, padding: Spacing.md, borderRadius: Radius.lg },
  landmarkBadge: { width: scale(44), height: scale(44), borderRadius: Radius.md, backgroundColor: Colors.primaryLight, justifyContent: 'center', alignItems: 'center' },
  landmarkBadgeIcon: { fontSize: scale(22) },
  landmarkName: { fontSize: scale(16), fontWeight: '700', color: Colors.textPrimary },
  confText: { fontSize: scale(12), color: Colors.success, fontWeight: '600', marginTop: scale(2) },
  scanFeedbackRow: { flexDirection: 'row', gap: Spacing.xs, marginTop: scale(6) },
  scanFeedbackBtn: { borderWidth: 1, borderColor: Colors.border, backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingVertical: scale(5), paddingHorizontal: scale(10) },
  scanFeedbackBtnText: { fontSize: scale(11), color: Colors.textPrimary, fontWeight: '600' },
  scanFeedbackThanks: { fontSize: scale(11), color: Colors.success, fontWeight: '600', marginTop: scale(6) },

  sectionTitle: { fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary, marginBottom: scale(6), marginTop: Spacing.sm },
  descText: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(20) },
  detHint: { fontSize: scale(11), color: Colors.textMuted, marginBottom: scale(8) },

  detCard: { backgroundColor: Colors.white, borderRadius: Radius.md, marginBottom: scale(8), borderLeftWidth: 4, overflow: 'hidden' },
  detCardHeader: { flexDirection: 'row', alignItems: 'center', padding: Spacing.md, gap: Spacing.sm },
  detDot: { width: scale(10), height: scale(10), borderRadius: scale(5) },
  detLabel: { flex: 1, fontSize: scale(13), fontWeight: '600', color: Colors.textPrimary },
  detConf: { fontSize: scale(11), color: Colors.textMuted, fontWeight: '600' },
  detChevron: { fontSize: scale(18), color: Colors.textMuted, fontWeight: '700' },
  detBody: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.md, gap: scale(8) },
  detDesc: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(20) },
  detSigBox: { backgroundColor: Colors.inputBg, borderRadius: Radius.sm, padding: scale(10) },
  detSigLabel: { fontSize: scale(11), fontWeight: '700', color: Colors.accent, marginBottom: scale(4) },
  detSig: { fontSize: scale(12), color: Colors.textSecondary, lineHeight: scale(18) },

  similarCard: { backgroundColor: Colors.white, borderRadius: Radius.md, padding: scale(10), marginRight: Spacing.sm, alignItems: 'center', width: scale(90) },
  similarIcon: { fontSize: scale(22), marginBottom: scale(4) },
  similarName: { fontSize: scale(10), fontWeight: '600', color: Colors.textPrimary, textAlign: 'center' },
  noDetails: { fontSize: scale(13), color: Colors.textMuted, textAlign: 'center', marginTop: Spacing.lg },

  contextPill: { backgroundColor: Colors.primaryLight, paddingVertical: scale(6), paddingHorizontal: Spacing.md },
  contextPillText: { fontSize: scale(11), color: Colors.primary, fontWeight: '600' },

  bubble: { padding: scale(10), borderRadius: Radius.lg, maxWidth: '85%' },
  aiBubble: { backgroundColor: Colors.white, alignSelf: 'flex-start', borderBottomLeftRadius: scale(4) },
  userBubble: { backgroundColor: Colors.primary, alignSelf: 'flex-end', borderBottomRightRadius: scale(4) },
  bubbleText: { fontSize: scale(13), color: Colors.textPrimary, lineHeight: scale(19) },

  suggestScroll: { maxHeight: scale(40) },
  suggestContent: { paddingHorizontal: Spacing.md, paddingBottom: Spacing.xs, gap: Spacing.xs, alignItems: 'center' },
  suggestBtn: { backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingVertical: scale(6), paddingHorizontal: scale(12) },
  suggestText: { fontSize: scale(11), color: Colors.textPrimary, fontWeight: '500' },

  rateSessionBtn: { marginHorizontal: Spacing.md, marginBottom: scale(6), backgroundColor: Colors.accentLight, borderRadius: Radius.full, paddingVertical: scale(9), alignItems: 'center', borderWidth: 1, borderColor: Colors.accent },
  rateSessionText: { color: Colors.accentDark, fontWeight: '700', fontSize: scale(13) },
  rateSessionDone: { marginHorizontal: Spacing.md, marginBottom: scale(6), alignItems: 'center', paddingVertical: scale(6) },
  rateSessionDoneText: { color: Colors.success, fontWeight: '600', fontSize: scale(12) },
  chatBar: { flexDirection: 'row', padding: Spacing.sm, backgroundColor: Colors.white, borderTopWidth: 1, borderTopColor: Colors.border, gap: Spacing.sm },
  chatInput: { flex: 1, backgroundColor: Colors.inputBg, borderRadius: Radius.full, paddingHorizontal: Spacing.md, paddingVertical: scale(8), fontSize: scale(13), color: Colors.textPrimary },
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
  modalSubmit: { flex: 1, padding: Spacing.sm, borderRadius: Radius.md, backgroundColor: Colors.primary, alignItems: 'center' },
});
