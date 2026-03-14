import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { getItineraries, deleteItinerary } from '@/api/client';

interface SavedTrip {
  id: string;
  name: string;
  createdAt: string;
  totalDuration?: number;
  stops?: { id: string }[];
}

export default function ItinerariesScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadTrips = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getItineraries();
      setTrips(data.itineraries || []);
    } catch {
      setError('Could not load itineraries. Make sure you are logged in.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadTrips(); }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteItinerary(id);
      setTrips(prev => prev.filter(t => t.id !== id));
    } catch {
      // silent
    }
  };

  const formatDate = (iso: string) => {
    try { return new Date(iso).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return iso; }
  };

  const formatDuration = (minutes?: number) => {
    if (!minutes) return '';
    if (minutes < 60) return `${minutes}m`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60 > 0 ? `${minutes % 60}m` : ''}`.trim();
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + Spacing.sm }]}>
        <Text style={styles.title}>My Itineraries</Text>
        <Text style={styles.subtitle}>
          Saved Plans • {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
        </Text>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={Colors.accent} size="large" />
          <Text style={styles.loadingText}>Loading your trips...</Text>
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={loadTrips}>
            <Text style={styles.retryText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      ) : trips.length === 0 ? (
        <View style={styles.empty}>
          <Text style={styles.emptyIcon}>🗺️</Text>
          <Text style={styles.emptyTitle}>No trips yet</Text>
          <Text style={styles.emptySubtitle}>Generate your first Penang itinerary!</Text>
          <TouchableOpacity style={styles.createBtn} onPress={() => router.push('/plan')}>
            <Text style={styles.createBtnText}>Plan a Trip ✨</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={trips}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.list}
          onRefresh={loadTrips}
          refreshing={loading}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.card}
              onPress={() => router.push({ pathname: '/itinerary', params: { id: item.id, name: item.name } })}
            >
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle} numberOfLines={2}>{item.name}</Text>
                <TouchableOpacity onPress={() => handleDelete(item.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                  <Text style={styles.deleteIcon}>🗑️</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.cardDate}>{formatDate(item.createdAt)}</Text>
              <View style={styles.cardMeta}>
                {item.stops && <Text style={styles.cardStat}>📍 {item.stops.length} stops</Text>}
                {item.totalDuration ? <Text style={styles.cardStat}>⏱️ {formatDuration(item.totalDuration)}</Text> : null}
              </View>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: { backgroundColor: Colors.primary, paddingHorizontal: Spacing.lg, paddingBottom: Spacing.lg },
  title: { fontSize: scale(20), fontWeight: '800', color: Colors.white },
  subtitle: { fontSize: scale(11), color: Colors.tabInactive, marginTop: scale(3) },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.xl, gap: Spacing.md },
  loadingText: { fontSize: scale(13), color: Colors.textMuted },
  errorText: { fontSize: scale(13), color: Colors.error, textAlign: 'center' },
  retryBtn: { backgroundColor: Colors.primary, borderRadius: Radius.full, paddingVertical: scale(10), paddingHorizontal: Spacing.lg },
  retryText: { color: Colors.white, fontWeight: '700', fontSize: scale(13) },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: Spacing.xl },
  emptyIcon: { fontSize: scale(48), marginBottom: Spacing.md },
  emptyTitle: { fontSize: scale(18), fontWeight: '700', color: Colors.textPrimary, marginBottom: scale(6) },
  emptySubtitle: { fontSize: scale(13), color: Colors.textSecondary, marginBottom: Spacing.lg },
  createBtn: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(12), paddingHorizontal: scale(24) },
  createBtnText: { color: Colors.white, fontSize: scale(14), fontWeight: '700' },
  list: { padding: Spacing.md, gap: Spacing.sm },
  card: { backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.md, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: Spacing.sm },
  cardTitle: { flex: 1, fontSize: scale(14), fontWeight: '700', color: Colors.textPrimary },
  deleteIcon: { fontSize: scale(16) },
  cardDate: { fontSize: scale(11), color: Colors.textMuted, marginTop: scale(3) },
  cardMeta: { flexDirection: 'row', gap: Spacing.md, marginTop: Spacing.sm },
  cardStat: { fontSize: scale(11), color: Colors.textSecondary, fontWeight: '500' },
});
