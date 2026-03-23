import { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, TextInput, Modal } from 'react-native';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Radius, Spacing, scale } from '@/constants/theme';
import { getStoredUser, logout, updateProfile } from '@/api/client';

export default function ProfileScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [interests, setInterests] = useState<string[]>([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editName, setEditName] = useState('');
  const [saving, setSaving] = useState(false);

  const loadProfileData = async () => {
    setProfileLoading(true);
    const localInterests = await AsyncStorage.getItem('user_interests');
    if (localInterests) {
      const parsedInterests = JSON.parse(localInterests);
      if (Array.isArray(parsedInterests)) {
        setInterests(parsedInterests);
      }
    }

    const user = await getStoredUser();
    if (user) {
      setEmail(user.email || '');
      setName(user.name || user.email?.split('@')[0] || 'User');
    }

    setProfileLoading(false);
  };

  useEffect(() => {
    void loadProfileData();
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadProfileData();
    }, [])
  );

  const handleEditName = () => {
    setEditName(name);
    setEditModalVisible(true);
  };

  const handleSaveName = async () => {
    if (!editName.trim()) return;
    setSaving(true);
    try {
      await updateProfile({ name: editName.trim() });
      setName(editName.trim());
      setEditModalVisible(false);
    } catch (err) {
      alert('Failed to update name');
    } finally {
      setSaving(false);
    }
  };

  const handleEditInterests = () => {
    router.push('/onboarding?mode=edit');
  };

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={[styles.header, { paddingTop: insets.top + Spacing.lg }]}>
        <View style={styles.avatar}><Text style={styles.avatarText}>👤</Text></View>
        <View style={styles.nameRow}>
          <Text style={styles.name}>{name}</Text>
          <TouchableOpacity onPress={handleEditName} style={styles.editNameBtn}>
            <Text style={styles.editNameText}>✏️</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.email}>{email}</Text>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Interests</Text>
          <TouchableOpacity onPress={handleEditInterests} style={styles.editInterestsBtn}>
            <Text style={styles.editInterestsText}>Edit</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.tagsRow}>
          {interests.map(i => <View key={i} style={styles.tag}><Text style={styles.tagText}>{i}</Text></View>)}
          {interests.length === 0 && <Text style={styles.noTags}>No interests selected</Text>}
        </View>
      </View>

      <View style={styles.menu}>
        {['Preferences', 'Settings', 'Help & Support'].map(item => (
          <TouchableOpacity key={item} style={styles.menuItem}>
            <Text style={styles.menuText}>{item}</Text>
            <Text style={styles.menuArrow}>›</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Logout</Text>
      </TouchableOpacity>

      <Modal visible={editModalVisible} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Edit Name</Text>
            <TextInput
              style={styles.input}
              value={editName}
              onChangeText={setEditName}
              placeholder="Enter your name"
              placeholderTextColor={Colors.tabInactive}
              autoFocus
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity onPress={() => setEditModalVisible(false)} style={styles.cancelBtn}>
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={handleSaveName} style={styles.saveBtn} disabled={saving}>
                <Text style={styles.saveText}>{saving ? 'Saving...' : 'Save'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { paddingBottom: scale(30) },
  header: { alignItems: 'center', paddingBottom: Spacing.xl, paddingTop: Spacing.xl },
  avatar: { 
    width: scale(70), 
    height: scale(70), 
    borderRadius: scale(35), 
    backgroundColor: Colors.white, 
    justifyContent: 'center', 
    alignItems: 'center', 
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  avatarText: { fontSize: scale(28) },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: scale(8) },
  name: { fontSize: scale(18), fontWeight: '700', color: Colors.textPrimary },
  editNameBtn: { padding: scale(4) },
  editNameText: { fontSize: scale(14) },
  email: { fontSize: scale(12), color: Colors.textSecondary, marginTop: scale(2) },
  section: { paddingHorizontal: Spacing.lg, marginBottom: Spacing.lg },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.sm },
  sectionTitle: { fontSize: scale(13), fontWeight: '700', color: Colors.textPrimary },
  editInterestsBtn: { 
    backgroundColor: Colors.white, 
    borderRadius: Radius.full, 
    paddingHorizontal: scale(12), 
    paddingVertical: scale(4),
    borderWidth: 1,
    borderColor: Colors.border,
  },
  editInterestsText: { color: Colors.textSecondary, fontSize: scale(11), fontWeight: '600' },
  tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm },
  tag: { backgroundColor: Colors.accentLight, borderRadius: Radius.full, paddingVertical: scale(5), paddingHorizontal: scale(12) },
  tagText: { color: Colors.accentDark, fontSize: scale(11), fontWeight: '600' },
  noTags: { color: Colors.textMuted, fontSize: scale(11) },
  menu: { 
    backgroundColor: Colors.white, 
    marginHorizontal: Spacing.lg, 
    borderRadius: Radius.lg, 
    marginBottom: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  menuItem: { 
    flexDirection: 'row', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    paddingVertical: scale(14), 
    paddingHorizontal: Spacing.md, 
    borderBottomWidth: 1, 
    borderBottomColor: Colors.border 
  },
  menuText: { fontSize: scale(14), color: Colors.textPrimary, fontWeight: '500' },
  menuArrow: { fontSize: scale(18), color: Colors.textMuted },
  logoutBtn: { 
    backgroundColor: Colors.white, 
    marginHorizontal: Spacing.lg, 
    borderRadius: Radius.lg, 
    paddingVertical: scale(14), 
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.error + '40', // Very light error border
  },
  logoutText: { color: Colors.error, fontSize: scale(14), fontWeight: '700' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', alignItems: 'center' },
  modalContent: { backgroundColor: Colors.white, borderRadius: Radius.lg, padding: Spacing.lg, width: '85%', maxWidth: scale(320) },
  modalTitle: { fontSize: scale(18), fontWeight: '700', color: Colors.textPrimary, marginBottom: Spacing.md },
  input: { 
    backgroundColor: Colors.background, 
    borderRadius: Radius.md, 
    padding: Spacing.md, 
    color: Colors.textPrimary, 
    fontSize: scale(14), 
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  modalButtons: { flexDirection: 'row', gap: Spacing.sm },
  cancelBtn: { flex: 1, backgroundColor: Colors.background, borderRadius: Radius.md, paddingVertical: scale(12), alignItems: 'center' },
  cancelText: { color: Colors.textSecondary, fontSize: scale(14), fontWeight: '600' },
  saveBtn: { flex: 1, backgroundColor: Colors.accent, borderRadius: Radius.md, paddingVertical: scale(12), alignItems: 'center' },
  saveText: { color: Colors.white, fontSize: scale(14), fontWeight: '700' },
});
