import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale, verticalScale } from '@/constants/theme';
import { registerUser } from '@/api/client';

export default function SignupScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [form, setForm] = useState({ firstName: '', lastName: '', phone: '', age: '', email: '', password: '' });
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const update = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const handleSignup = async () => {
    if (!form.email.trim() || !form.password.trim()) {
      setError('Email and password are required.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const displayName = [form.firstName, form.lastName].filter(Boolean).join(' ') || undefined;
      await registerUser(form.email.trim(), form.password, displayName);
      router.replace('/onboarding');
    } catch (e: any) {
      setError(e.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: Colors.white }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">

        {/* ── Branded header (matches Login screen) ── */}
        <View style={[styles.headerBg, { paddingTop: insets.top }]}>
          <TouchableOpacity onPress={() => router.back()} style={styles.headerBackBtn}>
            <Text style={styles.headerBackText}>‹</Text>
          </TouchableOpacity>
          <Text style={styles.logoIcon}>🏛️</Text>
        </View>

        <View style={styles.body}>
          <Text style={styles.title}>Create account</Text>
          <Text style={styles.subtitle}>Join PenangLens to discover and plan your Penang adventures.</Text>

          <Text style={styles.label}>First name</Text>
          <TextInput style={styles.input} placeholder="John" placeholderTextColor={Colors.textMuted} value={form.firstName} onChangeText={v => update('firstName', v)} />

          <Text style={styles.label}>Last name</Text>
          <TextInput style={styles.input} placeholder="Doe" placeholderTextColor={Colors.textMuted} value={form.lastName} onChangeText={v => update('lastName', v)} />

          <Text style={styles.label}>Phone</Text>
          <View style={styles.phoneRow}>
            <View style={styles.phoneCode}><Text style={styles.phoneCodeText}>+60</Text></View>
            <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]} placeholder="123 456 789" placeholderTextColor={Colors.textMuted} value={form.phone} onChangeText={v => update('phone', v)} keyboardType="phone-pad" />
          </View>

          <Text style={styles.label}>Age</Text>
          <TextInput style={styles.input} placeholder="25" placeholderTextColor={Colors.textMuted} value={form.age} onChangeText={v => update('age', v)} keyboardType="number-pad" />

          <Text style={styles.label}>Email</Text>
          <TextInput style={styles.input} placeholder="john@example.com" placeholderTextColor={Colors.textMuted} value={form.email} onChangeText={v => update('email', v)} keyboardType="email-address" autoCapitalize="none" />

          <Text style={styles.label}>Password</Text>
          <TextInput style={styles.input} placeholder="••••••••" placeholderTextColor={Colors.textMuted} value={form.password} onChangeText={v => update('password', v)} secureTextEntry />

          <TouchableOpacity style={styles.checkRow} onPress={() => setAgreed(!agreed)}>
            <View style={[styles.checkbox, agreed && styles.checked]}>
              {agreed && <Text style={styles.checkTick}>✓</Text>}
            </View>
            <Text style={styles.checkText}>I accept terms and conditions</Text>
          </TouchableOpacity>

          {error ? <Text style={styles.errorText}>{error}</Text> : null}

          <TouchableOpacity style={[styles.createBtn, (!agreed || loading) && { opacity: 0.5 }]} disabled={!agreed || loading} onPress={handleSignup}>
            <Text style={styles.createBtnText}>{loading ? 'Creating...' : 'Create Account'}</Text>
          </TouchableOpacity>

          <View style={styles.loginRow}>
            <Text style={styles.loginText}>Already have an account? </Text>
            <TouchableOpacity onPress={() => router.push('/login')}>
              <Text style={styles.loginLink}>Sign in</Text>
            </TouchableOpacity>
          </View>

          <Text style={[styles.footer, { marginBottom: Spacing.lg + insets.bottom }]}>PENANG<Text style={{ color: Colors.accent }}>LENS</Text></Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scrollContent: { flexGrow: 1 },

  // Header — matches login.tsx
  headerBg: {
    backgroundColor: Colors.primary,
    height: verticalScale(160),
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomLeftRadius: scale(30),
    borderBottomRightRadius: scale(30),
  },
  headerBackBtn: {
    position: 'absolute',
    top: 0,
    left: scale(16),
    width: scale(36),
    height: scale(36),
    borderRadius: scale(18),
    backgroundColor: 'rgba(255,255,255,0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerBackText: { fontSize: scale(22), color: Colors.white, fontWeight: '600', marginTop: -scale(2) },
  logoIcon: { fontSize: scale(48) },

  body: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg },
  title: { fontSize: scale(22), fontWeight: '800', color: Colors.textPrimary, marginBottom: scale(4) },
  subtitle: { fontSize: scale(12), color: Colors.textSecondary, marginBottom: Spacing.lg, lineHeight: scale(18) },

  label: { fontSize: scale(11), fontWeight: '600', color: Colors.textSecondary, marginBottom: Spacing.xs, marginTop: Spacing.sm },
  input: {
    backgroundColor: Colors.inputBg, borderRadius: Radius.md,
    paddingVertical: scale(11), paddingHorizontal: scale(14),
    fontSize: scale(14), color: Colors.textPrimary, marginBottom: Spacing.xs,
  },
  phoneRow: { flexDirection: 'row', gap: Spacing.sm, alignItems: 'center', marginBottom: Spacing.xs },
  phoneCode: { backgroundColor: Colors.inputBg, borderRadius: Radius.md, paddingVertical: scale(11), paddingHorizontal: scale(14) },
  phoneCodeText: { fontSize: scale(14), color: Colors.textPrimary, fontWeight: '500' },

  checkRow: { flexDirection: 'row', alignItems: 'center', gap: scale(8), marginTop: Spacing.md },
  checkbox: { width: scale(18), height: scale(18), borderRadius: 4, borderWidth: 1.5, borderColor: Colors.border, justifyContent: 'center', alignItems: 'center' },
  checked: { backgroundColor: Colors.accent, borderColor: Colors.accent },
  checkTick: { color: Colors.white, fontSize: scale(11), fontWeight: '700' },
  checkText: { fontSize: scale(12), color: Colors.textSecondary },

  errorText: { color: Colors.error, fontSize: scale(12), textAlign: 'center', marginTop: Spacing.sm, marginBottom: Spacing.xs },

  createBtn: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.md },
  createBtnText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },

  loginRow: { flexDirection: 'row', justifyContent: 'center', marginTop: Spacing.lg },
  loginText: { fontSize: scale(12), color: Colors.textSecondary },
  loginLink: { fontSize: scale(12), fontWeight: '700', color: Colors.accent },

  footer: { textAlign: 'center', fontSize: scale(14), fontWeight: '800', color: Colors.primary, marginTop: Spacing.xl, letterSpacing: 1, marginBottom: Spacing.lg },
});
