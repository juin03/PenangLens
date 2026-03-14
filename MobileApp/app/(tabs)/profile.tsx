import { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { getStoredUser, logout } from '@/api/client';

export default function ProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [interests, setInterests] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      const user = await getStoredUser();
      if (user) {
        setEmail(user.email || '');
        setInterests(user.interests || []);
      }
    })();
  }, []);

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={[styles.header, { paddingTop: insets.top + Spacing.lg }]}>
        <View style={styles.avatar}><Text style={styles.avatarText}>👤</Text></View>
        <Text style={styles.name}>{email || 'PenangLens User'}</Text>
        <Text style={styles.email}>{email}</Text>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.stat}><Text style={styles.statVal}>0</Text><Text style={styles.statLbl}>Visited</Text></View>
        <View style={styles.divider} />
        <View style={styles.stat}><Text style={styles.statVal}>0</Text><Text style={styles.statLbl}>Bucket List</Text></View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Interests</Text>
        <View style={styles.tagsRow}>
          {interests.map(i => <View key={i} style={styles.tag}><Text style={styles.tagText}>{i}</Text></View>)}
          {interests.length === 0 && <Text style={styles.noTags}>No interests selected</Text>}
        </View>
      </View>

      <View style={styles.menu}>
        {['Profile', 'Preferences', 'Settings', 'Help & Support'].map(item => (
          <TouchableOpacity key={item} style={styles.menuItem}>
            <Text style={styles.menuText}>{item}</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Logout</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.primary },
  content: { paddingBottom: scale(30) },
  header: { alignItems: 'center', paddingBottom: Spacing.lg },
  avatar: { width: scale(64), height: scale(64), borderRadius: scale(32), backgroundColor: 'rgba(255,255,255,0.12)', justifyContent: 'center', alignItems: 'center', marginBottom: Spacing.sm },
  avatarText: { fontSize: scale(28) },
  name: { fontSize: scale(16), fontWeight: '700', color: Colors.white },
  email: { fontSize: scale(11), color: Colors.tabInactive, marginTop: scale(2) },
  statsRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: Spacing.xl, marginBottom: Spacing.lg },
  stat: { alignItems: 'center' },
  statVal: { fontSize: scale(18), fontWeight: '800', color: Colors.white },
  statLbl: { fontSize: scale(10), color: Colors.tabInactive, marginTop: scale(2) },
  divider: { width: 1, height: scale(28), backgroundColor: 'rgba(255,255,255,0.15)' },
  section: { paddingHorizontal: Spacing.lg, marginBottom: Spacing.lg },
  sectionTitle: { fontSize: scale(12), fontWeight: '600', color: Colors.tabInactive, marginBottom: Spacing.sm },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  tag: { backgroundColor: Colors.accentLight, borderRadius: Radius.full, paddingVertical: scale(5), paddingHorizontal: scale(12) },
  tagText: { color: Colors.accent, fontSize: scale(11), fontWeight: '600' },
  noTags: { color: Colors.tabInactive, fontSize: scale(11) },
  menu: { backgroundColor: 'rgba(255,255,255,0.05)', marginHorizontal: Spacing.md, borderRadius: Radius.lg, marginBottom: Spacing.lg },
  menuItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: scale(13), paddingHorizontal: Spacing.md, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.05)' },
  menuText: { fontSize: scale(13), color: Colors.white, fontWeight: '500' },
  menuArrow: { fontSize: scale(18), color: Colors.tabInactive },
  logoutBtn: { backgroundColor: Colors.error, marginHorizontal: Spacing.md, borderRadius: Radius.lg, paddingVertical: scale(13), alignItems: 'center' },
  logoutText: { color: Colors.white, fontSize: scale(14), fontWeight: '700' },
});
