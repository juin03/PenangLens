import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, FlatList, ActivityIndicator, Image, Modal, KeyboardAvoidingView, Platform,
} from 'react-native';
import MapView, { PROVIDER_GOOGLE, Marker, Callout, Region } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { streamChat } from '@/api/streaming';
import { MarkdownText } from '@/components/MarkdownText';
import { Colors, Radius, Spacing, scale, SCREEN_WIDTH } from '@/constants/theme';
import { API_BASE_URL, getToken } from '@/api/client';

// Derive the BFF base URL from the shared client (single source of truth for LAN IP)
const BFF_BASE = API_BASE_URL.replace('/api/v1', '');
const MAP_API = `${BFF_BASE}/api/spots/map`;

const CATEGORIES = ['All', 'Heritage', 'Food', 'Nature', 'Art', 'Religious', 'Shopping', 'Culture', 'Architecture'];
const CARD_WIDTH = (SCREEN_WIDTH - Spacing.lg * 2 - Spacing.sm) / 2;
const PENANG_REGION: Region = { latitude: 5.4164, longitude: 100.3327, latitudeDelta: 0.18, longitudeDelta: 0.18 };

interface MapSpot {
  id: string; name: string; type: string; status: string;
  lat: number; lng: number; description?: string; tags?: string[];
  parentLandmark?: string;
  firstImageUrl?: string | null;
}

export default function DiscoverScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [spots, setSpots] = useState<MapSpot[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Chat state
  interface ChatMsg { role: 'user' | 'assistant'; content: string }
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: 'assistant', content: 'Hi! Ask me anything about Penang — places to visit, food, history, tips 🌴' },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatThreadId, setChatThreadId] = useState<string | undefined>();
  const chatListRef = useRef<FlatList>(null);
  // Per-session chat rating (1–5 stars)
  const [chatRated, setChatRated] = useState(false);
  const [chatRatingModalVisible, setChatRatingModalVisible] = useState(false);
  const [chatStars, setChatStars] = useState(0);
  const [chatComment, setChatComment] = useState('');
  const userChatCount = chatMessages.filter(m => m.role === 'user').length;

  const submitChatRating = async (stars: number, comment?: string) => {
    setChatRated(true);
    try {
      const BASE = API_BASE_URL.replace('/api/v1', '');
      const token = await getToken();
      await fetch(`${BASE}/api/v1/feedback/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ rating: stars, comment: comment || undefined, context: 'Ask about Penang', threadId: chatThreadId, messageCount: userChatCount }),
      });
    } catch {}
  };

  const sendChat = async () => {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', content: msg }]);
    setChatLoading(true);
    const aiIdx = chatMessages.length + 1;
    setChatMessages(prev => [...prev, { role: 'assistant', content: '' }]);
    try {
      const stream = streamChat(msg, chatThreadId ?? `discover_${Date.now()}`, undefined, 'general_chat');
      let full = '';
      for await (const update of stream) {
        if (update.type === 'chunk') {
          full += update.content;
          setChatMessages(prev => { const m = [...prev]; m[aiIdx] = { role: 'assistant', content: full }; return m; });
        } else if (update.type === 'complete') {
          setChatThreadId(update.data?.thread_id);
        }
      }
    } catch {
      setChatMessages(prev => { const m = [...prev]; m[aiIdx] = { role: 'assistant', content: 'Connection error. Try again.' }; return m; });
    } finally { setChatLoading(false); }
  };

  const loadSpots = useCallback(async () => {
    try {
      const interestsRaw = await AsyncStorage.getItem('user_interests');
      const interests = interestsRaw ? JSON.parse(interestsRaw) : [];
      const hasInterests = Array.isArray(interests) && interests.length > 0;
      const url = hasInterests
        ? `${MAP_API}?interests=${encodeURIComponent(interests.join(','))}`
        : MAP_API;

      const response = await fetch(url);
      const data = await response.json();
      setSpots(data.spots || []);
    } catch {
      setSpots([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadSpots();
  }, [loadSpots]);

  useFocusEffect(
    useCallback(() => {
      void loadSpots();
    }, [loadSpots])
  );

  const onRefresh = () => {
    setRefreshing(true);
    void loadSpots();
  };

  const filteredSpots = spots.filter(s => {
    const matchSearch = s.name.toLowerCase().includes(search.toLowerCase());
    const matchCat = activeCategory === 'All' || (s.tags || []).includes(activeCategory) || s.type === activeCategory.toLowerCase();
    return matchSearch && matchCat;
  });

  const pinColor = (s: MapSpot) => s.type === 'landmark' ? '#2563eb' : '#22c55e';

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + Spacing.sm }]}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.greeting}>Discover Penang 🌴</Text>
            <Text style={styles.subGreeting}>Find heritage sites, attractions & more.</Text>
          </View>
          {/* View toggle */}
          <View style={styles.toggleRow}>
            <TouchableOpacity
              style={[styles.toggleBtn, viewMode === 'list' && styles.toggleActive]}
              onPress={() => setViewMode('list')}>
              <Text style={[styles.toggleText, viewMode === 'list' && styles.toggleTextActive]}>☰</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.toggleBtn, viewMode === 'map' && styles.toggleActive]}
              onPress={() => setViewMode('map')}>
              <Text style={[styles.toggleText, viewMode === 'map' && styles.toggleTextActive]}>🗺</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* Search */}
      <View style={styles.searchWrap}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search places, landmarks..."
          placeholderTextColor={Colors.textMuted}
          value={search}
          onChangeText={setSearch}
        />
      </View>

      {/* Category chips */}
      <View style={styles.chipSection}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll} contentContainerStyle={styles.chipRow}>
        {CATEGORIES.map(cat => (
          <TouchableOpacity key={cat} style={[styles.chip, activeCategory === cat && styles.chipActive]} onPress={() => setActiveCategory(cat)}>
            <Text
              numberOfLines={1}
              allowFontScaling={false}
              style={[styles.chipText, activeCategory === cat && styles.chipTextActive]}
            >
              {cat}
            </Text>
          </TouchableOpacity>
        ))}
        </ScrollView>
      </View>

      {/* ─── MAP VIEW ─── */}
      {viewMode === 'map' && (
        <View style={styles.mapContainer}>
          {loading ? (
            <View style={styles.mapLoading}>
              <ActivityIndicator color={Colors.primary} />
              <Text style={styles.mapLoadingText}>Loading map...</Text>
            </View>
          ) : (
            <MapView
              style={styles.map}
              provider={PROVIDER_GOOGLE}
              initialRegion={PENANG_REGION}
              showsUserLocation
              showsMyLocationButton>
              {filteredSpots.map(spot => (
                <Marker
                  key={spot.id}
                  coordinate={{ latitude: spot.lat, longitude: spot.lng }}
                  pinColor={pinColor(spot)}
                  title={spot.name}>
                  <Callout tooltip onPress={() => router.push({ pathname: '/landmark/[id]', params: { id: spot.id, name: spot.name } })}>
                    <View style={styles.callout}>
                      <Text style={styles.calloutTitle}>{spot.name}</Text>
                      <Text style={styles.calloutType}>{spot.type === 'landmark' ? '🏛️ Landmark' : '📍 Point of Interest'}</Text>
                      {spot.description && <Text style={styles.calloutDesc} numberOfLines={2}>{spot.description}</Text>}
                      <Text style={styles.calloutTap}>Tap to learn more →</Text>
                    </View>
                  </Callout>
                </Marker>
              ))}
            </MapView>
          )}
          {!loading && filteredSpots.length === 0 && (
            <View style={styles.mapEmpty}>
              <Text style={styles.mapEmptyText}>No published spots yet.{'\n'}The admin is still adding locations.</Text>
            </View>
          )}
        </View>
      )}

      {/* ─── LIST VIEW ─── */}
      {viewMode === 'list' && (
        <>
          <Text style={styles.sectionTitle}>
            {loading ? 'Loading...' : `${filteredSpots.length} ${activeCategory === 'All' ? 'Places' : activeCategory + ' Spots'}`}
          </Text>
          {loading ? (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : (
            <FlatList
              data={filteredSpots}
              keyExtractor={item => item.id}
              numColumns={2}
              refreshing={refreshing}
              onRefresh={onRefresh}
              columnWrapperStyle={styles.gridRow}
              contentContainerStyle={styles.gridContent}
              ListEmptyComponent={
                <View style={{ padding: Spacing.xl, alignItems: 'center' }}>
                  <Text style={{ color: Colors.textMuted, fontSize: scale(13), textAlign: 'center' }}>
                    No spots published yet.{'\n'}Check back soon!
                  </Text>
                </View>
              }
              renderItem={({ item }) => {
                const imgUri = item.firstImageUrl
                  ? (item.firstImageUrl.startsWith('http')
                    ? item.firstImageUrl
                    : `${BFF_BASE}${item.firstImageUrl}`)
                  : null;
                return (
                  <TouchableOpacity
                    style={[styles.placeCard, { width: CARD_WIDTH }]}
                    onPress={() => router.push({ pathname: '/landmark/[id]', params: { id: item.id, name: item.name } })}>
                    {imgUri ? (
                      <Image
                        source={{ uri: imgUri }}
                        style={styles.placeImg}
                        resizeMode="cover"
                      />
                    ) : (
                      <View style={[styles.placeImg, { backgroundColor: item.type === 'landmark' ? '#dbeafe' : '#dcfce7', justifyContent: 'center', alignItems: 'center' }]}>
                        <Text style={styles.placeIcon}>{item.type === 'landmark' ? '🏛️' : '📍'}</Text>
                      </View>
                    )}
                    <View style={styles.placeBody}>
                      <Text style={styles.placeName} numberOfLines={2}>{item.name}</Text>
                      <View style={styles.placeRow}>
                        <Text style={styles.placeType}>{item.type === 'landmark' ? 'Landmark' : 'POI'}</Text>
                        {item.parentLandmark && (
                          <Text style={styles.placeDist} numberOfLines={1}>{item.parentLandmark}</Text>
                        )}
                      </View>
                    </View>
                  </TouchableOpacity>
                );
              }}
            />
          )}
        </>
      )}

      {/* Floating chat button */}
      <TouchableOpacity
        style={[styles.fab, { backgroundColor: Colors.accent, position: 'absolute', bottom: 20, right: 16 }]}
        onPress={() => setChatOpen(true)}>
        <Ionicons name="chatbubble-ellipses" size={16} color={Colors.white} />
        <Text style={styles.fabText}>Ask AI</Text>
      </TouchableOpacity>

      {/* Chat Modal */}
      <Modal visible={chatOpen} animationType="slide" transparent onRequestClose={() => setChatOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
          <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)' }}>
            <View style={{ flex: 1, marginTop: insets.top + 20, backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, overflow: 'hidden' }}>
              {/* Header */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: Colors.border }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="chatbubble-ellipses" size={20} color={Colors.primary} />
                  <Text style={{ fontSize: 17, fontWeight: '700', color: Colors.text }}>Ask about Penang</Text>
                </View>
                <View style={{ flexDirection: 'row', gap: 16, alignItems: 'center' }}>
                  <TouchableOpacity onPress={() => {
                    setChatMessages([{ role: 'assistant', content: 'Hi! Ask me anything about Penang — places to visit, food, history, tips 🌴' }]);
                    setChatThreadId(undefined);
                    setChatRated(false);
                  }}>
                    <Text style={{ fontSize: 14, color: Colors.primary }}>Reset</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => setChatOpen(false)}>
                    <Text style={{ fontSize: 22, color: '#94a3b8' }}>✕</Text>
                  </TouchableOpacity>
                </View>
              </View>
              {/* Messages */}
              <FlatList
                ref={chatListRef}
                data={chatMessages}
                keyExtractor={(_, i) => String(i)}
                contentContainerStyle={{ padding: 16, paddingBottom: 8 }}
                onContentSizeChange={() => chatListRef.current?.scrollToEnd({ animated: true })}
                renderItem={({ item }) => (
                  <View style={{
                    alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%', marginBottom: 8,
                    backgroundColor: item.role === 'user' ? Colors.primary : Colors.white,
                    borderRadius: Radius.lg, padding: scale(10),
                    borderBottomRightRadius: item.role === 'user' ? scale(4) : Radius.lg,
                    borderBottomLeftRadius: item.role === 'user' ? Radius.lg : scale(4),
                    borderWidth: item.role === 'user' ? 0 : 1,
                    borderColor: Colors.border,
                  }}>
                    {item.role === 'user' ? (
                      <Text style={{ color: Colors.white, fontSize: scale(13) }}>{item.content}</Text>
                    ) : (
                      <MarkdownText style={{ fontSize: scale(13), color: Colors.text }}>{item.content || '...'}</MarkdownText>
                    )}
                  </View>
                )}
              />
              {/* Rate this conversation */}
              {userChatCount > 0 && !chatRated && (
                <TouchableOpacity
                  style={{ marginHorizontal: 12, marginBottom: 6, backgroundColor: Colors.accentLight, borderRadius: 20, paddingVertical: 9, alignItems: 'center', borderWidth: 1, borderColor: Colors.accent }}
                  onPress={() => { setChatStars(0); setChatComment(''); setChatRatingModalVisible(true); }}>
                  <Text style={{ color: Colors.accentDark, fontWeight: '700', fontSize: scale(13) }}>⭐ Rate this conversation</Text>
                </TouchableOpacity>
              )}
              {chatRated && (
                <View style={{ marginHorizontal: 12, marginBottom: 6, alignItems: 'center', paddingVertical: 6 }}>
                  <Text style={{ color: Colors.success, fontWeight: '600', fontSize: scale(12) }}>✓ Thanks for your feedback!</Text>
                </View>
              )}
              {/* Input */}
              <View style={{ flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: Colors.border, paddingBottom: 12, gap: 8 }}>
                <TextInput
                  style={{ flex: 1, backgroundColor: Colors.backgroundAlt || '#f1f5f9', borderRadius: 20, paddingHorizontal: 16, paddingVertical: 10, fontSize: scale(13) }}
                  placeholder="Ask anything about Penang..."
                  placeholderTextColor={Colors.textMuted}
                  value={chatInput}
                  onChangeText={setChatInput}
                  onSubmitEditing={sendChat}
                  editable={!chatLoading}
                />
                <TouchableOpacity
                  onPress={sendChat}
                  disabled={chatLoading || !chatInput.trim()}
                  style={{ backgroundColor: chatInput.trim() ? Colors.primary : Colors.border, borderRadius: 20, width: 40, height: 40, alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ color: Colors.white, fontSize: 16 }}>↑</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Chat rating modal */}
      <Modal visible={chatRatingModalVisible} transparent animationType="fade" onRequestClose={() => setChatRatingModalVisible(false)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 }}>
          <View style={{ backgroundColor: '#fff', borderRadius: 16, padding: 20 }}>
            <Text style={{ fontSize: 16, fontWeight: '700', color: Colors.textPrimary, textAlign: 'center' }}>How was this conversation?</Text>
            <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginVertical: 14 }}>
              {[1, 2, 3, 4, 5].map(star => (
                <TouchableOpacity key={star} onPress={() => setChatStars(star)}>
                  <Text style={{ fontSize: 32, color: star <= chatStars ? '#f59e0b' : Colors.border }}>{star <= chatStars ? '★' : '☆'}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput
              style={{ backgroundColor: '#f1f5f9', borderRadius: 10, padding: 12, fontSize: scale(13), minHeight: 60, textAlignVertical: 'top' }}
              placeholder="Optional comment..."
              placeholderTextColor={Colors.textMuted}
              value={chatComment}
              onChangeText={setChatComment}
              multiline
            />
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 14 }}>
              <TouchableOpacity style={{ flex: 1, padding: 12, borderRadius: 10, alignItems: 'center', backgroundColor: '#f1f5f9' }} onPress={() => setChatRatingModalVisible(false)}>
                <Text style={{ color: Colors.textSecondary }}>Skip</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={{ flex: 1, padding: 12, borderRadius: 10, alignItems: 'center', backgroundColor: Colors.primary, opacity: chatStars === 0 ? 0.5 : 1 }}
                disabled={chatStars === 0}
                onPress={async () => { await submitChatRating(chatStars, chatComment.trim() || undefined); setChatRatingModalVisible(false); }}>
                <Text style={{ color: Colors.white, fontWeight: '700' }}>Submit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.lg, paddingBottom: Spacing.lg },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  greeting: { fontSize: scale(20), fontWeight: '800', color: Colors.white },
  subGreeting: { fontSize: scale(11), color: Colors.headerSubtitle, marginTop: scale(3) },

  toggleRow: { flexDirection: 'row', backgroundColor: 'rgba(255,255,255,0.2)', borderRadius: Radius.md },
  toggleBtn: { padding: scale(8), paddingHorizontal: scale(12), borderRadius: Radius.md },
  toggleActive: { backgroundColor: Colors.white },
  toggleText: { fontSize: scale(14), color: Colors.tabInactive },
  toggleTextActive: { color: Colors.primary },

  searchWrap: { paddingHorizontal: Spacing.md, marginTop: scale(-16) },
  searchInput: {
    backgroundColor: Colors.white, borderRadius: Radius.full,
    paddingVertical: scale(10), paddingHorizontal: Spacing.md,
    fontSize: scale(13), color: Colors.textPrimary,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 8, elevation: 4,
  },
  chipSection: { marginTop: Spacing.lg, minHeight: scale(52), justifyContent: 'center' },
  chipScroll: { flexGrow: 0 },
  chipRow: { paddingHorizontal: Spacing.md, alignItems: 'center', paddingVertical: scale(6) },
  chip: {
    backgroundColor: Colors.white, borderRadius: Radius.full,
    paddingHorizontal: scale(14),
    paddingVertical: scale(8),
    minHeight: scale(38),
    justifyContent: 'center',
    marginRight: Spacing.sm,
    flexShrink: 0,
    borderWidth: 1, borderColor: Colors.border,
  },
  chipActive: { backgroundColor: Colors.accent, borderColor: Colors.accent },
  chipText: {
    fontSize: scale(12),
    fontWeight: '600',
    color: Colors.textSecondary,
  },
  chipTextActive: { color: Colors.white },

  // Map
  mapContainer: { flex: 1, marginTop: Spacing.sm },
  map: { flex: 1 },
  mapLoading: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: Spacing.sm },
  mapLoadingText: { fontSize: scale(13), color: Colors.textMuted },
  mapEmpty: {
    position: 'absolute', top: '40%', left: Spacing.xl, right: Spacing.xl,
    backgroundColor: 'rgba(255,255,255,0.95)', borderRadius: Radius.lg,
    padding: Spacing.lg, alignItems: 'center',
  },
  mapEmptyText: { fontSize: scale(13), color: Colors.textMuted, textAlign: 'center' },

  callout: {
    backgroundColor: Colors.white, borderRadius: Radius.md,
    padding: Spacing.sm, minWidth: 180, maxWidth: 240,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.15, shadowRadius: 6, elevation: 4,
  },
  calloutTitle: { fontSize: scale(13), fontWeight: '700', color: Colors.textPrimary, marginBottom: 2 },
  calloutType: { fontSize: scale(11), color: Colors.textMuted, marginBottom: 3 },
  calloutDesc: { fontSize: scale(11), color: Colors.textSecondary, marginBottom: 4 },
  calloutTap: { fontSize: scale(11), color: Colors.accent, fontWeight: '600' },

  // List
  sectionTitle: { fontSize: scale(15), fontWeight: '700', color: Colors.textPrimary, paddingHorizontal: Spacing.lg, marginTop: Spacing.sm, marginBottom: Spacing.sm },
  gridRow: { gap: Spacing.sm, paddingHorizontal: Spacing.lg },
  gridContent: { paddingBottom: scale(100), gap: Spacing.sm },
  placeCard: {
    backgroundColor: Colors.white, borderRadius: Radius.lg, overflow: 'hidden',
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2,
  },
  placeImg: { height: scale(80), justifyContent: 'center', alignItems: 'center' },
  placeIcon: { fontSize: scale(28) },
  placeBody: { padding: scale(8) },
  placeName: { fontSize: scale(12), fontWeight: '700', color: Colors.textPrimary },
  placeRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: scale(3) },
  placeType: { fontSize: scale(10), color: Colors.textSecondary },
  placeDist: { fontSize: scale(10), color: Colors.textMuted, flex: 1, textAlign: 'right' },

  fab: {
    backgroundColor: Colors.accent, borderRadius: Radius.full,
    flexDirection: 'row', alignItems: 'center', gap: scale(6),
    paddingVertical: scale(12), paddingHorizontal: scale(20),
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 10, elevation: 6,
  },
  fabIcon: { fontSize: scale(14) },
  fabText: { color: Colors.white, fontSize: scale(13), fontWeight: '700' },
});
