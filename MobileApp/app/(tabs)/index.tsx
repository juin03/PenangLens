import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, FlatList, ActivityIndicator, Image,
} from 'react-native';
import MapView, { PROVIDER_GOOGLE, Marker, Callout, Region } from 'react-native-maps';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Radius, Spacing, scale, SCREEN_WIDTH } from '@/constants/theme';
import { API_BASE_URL } from '@/api/client';

// Derive the BFF base URL from the shared client (single source of truth for LAN IP)
const BFF_BASE = API_BASE_URL.replace('/api/v1', '');
const MAP_API = `${BFF_BASE}/api/spots/map`;

const CATEGORIES = ['All', 'Heritage', 'Food', 'Nature', 'Art', 'Religious', 'Shopping', 'Historical', 'Architecture'];
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

      {/* Floating Plan Itinerary button */}
      <TouchableOpacity style={styles.fab} onPress={() => router.push('/plan')}>
        <Text style={styles.fabIcon}>✨</Text>
        <Text style={styles.fabText}>Plan Itinerary</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.lg, paddingBottom: Spacing.lg },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  greeting: { fontSize: scale(20), fontWeight: '800', color: Colors.white },
  subGreeting: { fontSize: scale(11), color: Colors.tabInactive, marginTop: scale(3) },

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
    position: 'absolute', bottom: scale(16), alignSelf: 'center',
    backgroundColor: Colors.accent, borderRadius: Radius.full,
    flexDirection: 'row', alignItems: 'center', gap: scale(6),
    paddingVertical: scale(12), paddingHorizontal: scale(20),
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.2, shadowRadius: 10, elevation: 6,
  },
  fabIcon: { fontSize: scale(14) },
  fabText: { color: Colors.white, fontSize: scale(13), fontWeight: '700' },
});
