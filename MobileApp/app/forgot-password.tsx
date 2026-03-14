import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale, verticalScale } from '@/constants/theme';

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');

  return (
    <ScrollView style={{ flex: 1, backgroundColor: Colors.white }} contentContainerStyle={[styles.content, { paddingTop: insets.top + Spacing.lg }]} keyboardShouldPersistTaps="handled">
      <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
        <Text style={styles.backText}>‹</Text>
      </TouchableOpacity>

      <View style={styles.iconWrap}><Text style={styles.icon}>🏛️</Text></View>

      <Text style={styles.title}>Forgot password</Text>
      <Text style={styles.subtitle}>
        Enter your email or phone no and we'll send the verification link to reset your password.
      </Text>

      <TextInput
        style={styles.input}
        placeholder="john.xyz@gmail.com"
        placeholderTextColor={Colors.textMuted}
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />

      <TouchableOpacity style={styles.button} onPress={() => router.back()}>
        <Text style={styles.buttonText}>Request code</Text>
      </TouchableOpacity>

      <Text style={styles.footer}>PENANG<Text style={{ color: Colors.accent }}>LENS</Text></Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: Spacing.lg },
  backBtn: { width: scale(32), height: scale(32), borderRadius: scale(16), backgroundColor: Colors.inputBg, justifyContent: 'center', alignItems: 'center', marginBottom: Spacing.lg },
  backText: { fontSize: scale(20), color: Colors.textPrimary, fontWeight: '600', marginTop: -2 },
  iconWrap: { alignItems: 'center', marginBottom: Spacing.lg },
  icon: { fontSize: scale(48) },
  title: { fontSize: scale(22), fontWeight: '800', color: Colors.textPrimary, marginBottom: scale(6) },
  subtitle: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(20), marginBottom: Spacing.lg },
  input: {
    backgroundColor: Colors.inputBg, borderRadius: Radius.md,
    paddingVertical: scale(12), paddingHorizontal: scale(14),
    fontSize: scale(14), color: Colors.textPrimary, marginBottom: Spacing.lg,
  },
  button: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(13), alignItems: 'center' },
  buttonText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },
  footer: { textAlign: 'center', fontSize: scale(14), fontWeight: '800', color: Colors.primary, marginTop: verticalScale(60), letterSpacing: 1 },
});
