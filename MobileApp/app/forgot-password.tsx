import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors, Radius, Spacing, scale, verticalScale } from '@/constants/theme';
import { forgotPassword, resetPassword } from '@/api/client';

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [step, setStep] = useState<'request' | 'reset'>('request');
  const [loading, setLoading] = useState(false);

  const handleRequest = async () => {
    if (!email.trim()) return Alert.alert('Error', 'Please enter your email.');
    setLoading(true);
    try {
      const res = await forgotPassword(email.trim());
      // Dev mode: token returned directly. Production: would arrive via email.
      if (res.resetToken) {
        setToken(res.resetToken);
        Alert.alert('Dev Mode', `Reset token: ${res.resetToken}\n\nIn production this would be emailed.`);
      }
      setStep('reset');
    } catch {
      Alert.alert('Error', 'Could not send reset request. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!token.trim() || !newPassword.trim()) return Alert.alert('Error', 'Please fill in all fields.');
    setLoading(true);
    try {
      await resetPassword(token.trim(), newPassword.trim());
      Alert.alert('Success', 'Password reset successfully.', [{ text: 'Login', onPress: () => router.replace('/login') }]);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Reset failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: Colors.white }}
      contentContainerStyle={styles.scrollContent}
      keyboardShouldPersistTaps="handled"
    >
      {/* ── Branded header (matches Login screen) ── */}
      <View style={[styles.headerBg, { paddingTop: insets.top }]}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBackBtn}>
          <Text style={styles.headerBackText}>‹</Text>
        </TouchableOpacity>
        <Text style={styles.logoIcon}>🏛️</Text>
      </View>

      <View style={styles.body}>
        <Text style={styles.title}>Forgot password</Text>

        {step === 'request' ? (
          <>
            <Text style={styles.subtitle}>Enter your email and we'll send a verification code to reset your password.</Text>
            <Text style={styles.label}>Email address</Text>
            <TextInput
              style={styles.input}
              placeholder="john.xyz@gmail.com"
              placeholderTextColor={Colors.textMuted}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <TouchableOpacity style={[styles.button, loading && { opacity: 0.6 }]} onPress={handleRequest} disabled={loading}>
              {loading
                ? <ActivityIndicator color={Colors.white} />
                : <Text style={styles.buttonText}>Request code</Text>}
            </TouchableOpacity>
          </>
        ) : (
          <>
            <Text style={styles.subtitle}>Enter the reset code and your new password.</Text>
            <Text style={styles.label}>Reset code</Text>
            <TextInput
              style={styles.input}
              placeholder="Reset code"
              placeholderTextColor={Colors.textMuted}
              value={token}
              onChangeText={setToken}
              autoCapitalize="none"
            />
            <Text style={styles.label}>New password</Text>
            <TextInput
              style={styles.input}
              placeholder="New password"
              placeholderTextColor={Colors.textMuted}
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
            />
            <TouchableOpacity style={[styles.button, loading && { opacity: 0.6 }]} onPress={handleReset} disabled={loading}>
              {loading
                ? <ActivityIndicator color={Colors.white} />
                : <Text style={styles.buttonText}>Reset password</Text>}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setStep('request')} style={styles.backLink}>
              <Text style={styles.backLinkText}>← Back to email</Text>
            </TouchableOpacity>
          </>
        )}

        <Text style={[styles.footer, { marginBottom: Spacing.lg + insets.bottom }]}>PENANG<Text style={{ color: Colors.accent }}>LENS</Text></Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: { flexGrow: 1 },

  // Header — matches login.tsx & signup.tsx
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
  title: { fontSize: scale(22), fontWeight: '800', color: Colors.textPrimary, marginBottom: scale(6) },
  subtitle: { fontSize: scale(13), color: Colors.textSecondary, lineHeight: scale(20), marginBottom: Spacing.lg },

  label: { fontSize: scale(11), fontWeight: '600', color: Colors.textSecondary, marginBottom: Spacing.xs, marginTop: Spacing.sm },
  input: {
    backgroundColor: Colors.inputBg, borderRadius: Radius.md,
    paddingVertical: scale(12), paddingHorizontal: scale(14),
    fontSize: scale(14), color: Colors.textPrimary, marginBottom: Spacing.sm,
  },
  button: { backgroundColor: Colors.accent, borderRadius: Radius.full, paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.xs },
  buttonText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },

  backLink: { marginTop: Spacing.md, alignItems: 'center' },
  backLinkText: { color: Colors.accent, fontSize: scale(13), fontWeight: '500' },

  footer: { textAlign: 'center', fontSize: scale(14), fontWeight: '800', color: Colors.primary, marginTop: Spacing.xxl, letterSpacing: 1 },
});
