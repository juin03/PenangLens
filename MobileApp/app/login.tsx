import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, Image,
  ScrollView, KeyboardAvoidingView, Platform
} from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors, Radius, Spacing, scale, verticalScale } from '@/constants/theme';
import { loginUser, registerUser } from '@/api/client';

export default function LoginScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      setError('Please fill in all fields.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await loginUser(email.trim(), password);
      // Check if user has completed onboarding
      const interests = await AsyncStorage.getItem('user_interests');
      if (interests) {
        router.replace('/(tabs)');
      } else {
        router.replace('/onboarding');
      }
    } catch (e: any) {
      setError(e.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDevSkip = async () => {
    try {
      // Try to register dev user, if exists just login
      try {
        await registerUser('dev@penanglens.com', 'dev123', 'Dev User', ['Food', 'Heritage', 'Art']);
      } catch {
        await loginUser('dev@penanglens.com', 'dev123');
      }
      await AsyncStorage.setItem('user_interests', JSON.stringify(['Food', 'Heritage', 'Art']));
      router.replace('/(tabs)');
    } catch {
      // Fallback: skip with mock token
      await AsyncStorage.setItem('auth_token', 'dev_token');
      router.replace('/(tabs)');
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: Colors.white }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Header illustration area */}
        <View style={[styles.headerBg, { paddingTop: insets.top }]}>
          <Image source={require("@/assets/images/logo.png")} style={{ width: scale(100), height: scale(100), borderRadius: scale(50) }} />
        </View>

        <View style={styles.body}>
          <Text style={styles.welcome}>Welcome to <Text style={styles.brand}>PENANG<Text style={styles.brandAccent}>LENS</Text></Text></Text>
          <Text style={styles.subtitle}>Please choose your login option below.</Text>

          {/* Email */}
          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            placeholder="Your email address"
            placeholderTextColor={Colors.textMuted}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
          />

          {/* Password */}
          <Text style={styles.label}>Password</Text>
          <View style={styles.passwordRow}>
            <TextInput
              style={[styles.input, { flex: 1, marginBottom: 0 }]}
              placeholder="Your password"
              placeholderTextColor={Colors.textMuted}
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
            />
            <TouchableOpacity style={styles.eyeBtn} onPress={() => setShowPassword(!showPassword)}>
              <Text style={styles.eyeIcon}>{showPassword ? '👁️' : '👁️‍🗨️'}</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity onPress={() => router.push('/forgot-password')}>
            <Text style={styles.forgotLink}>Forgot password?</Text>
          </TouchableOpacity>

          {error ? <Text style={styles.errorText}>{error}</Text> : null}

          {/* Login */}
          <TouchableOpacity
            style={[styles.loginBtn, loading && { opacity: 0.6 }]}
            onPress={handleLogin}
            disabled={loading}
          >
            <Text style={styles.loginBtnText}>{loading ? 'Logging in...' : 'Login'}</Text>
          </TouchableOpacity>
          {/* Signup */}
          <View style={styles.signupRow}>
            <Text style={styles.signupText}>Don't have account to discuss? </Text>
            <TouchableOpacity onPress={() => router.push('/signup')}>
              <Text style={styles.signupLink}>Create Account</Text>
            </TouchableOpacity>
          </View>

          <Text style={[styles.footer, { marginBottom: Spacing.lg + insets.bottom }]}>PENANG<Text style={styles.brandAccent}>LENS</Text></Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scrollContent: { flexGrow: 1 },
  headerBg: {
    backgroundColor: Colors.primary,
    height: verticalScale(180),
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomLeftRadius: scale(30),
    borderBottomRightRadius: scale(30),
  },
  logoIcon: { fontSize: scale(56) },
  body: { paddingHorizontal: Spacing.lg, paddingTop: Spacing.lg },
  welcome: { fontSize: scale(16), color: Colors.textSecondary, textAlign: 'center' },
  brand: { fontSize: scale(20), fontWeight: '900', color: Colors.primary },
  brandAccent: { color: Colors.accent },
  subtitle: { fontSize: scale(12), color: Colors.textMuted, textAlign: 'center', marginBottom: Spacing.lg },
  label: { fontSize: scale(12), fontWeight: '600', color: Colors.textSecondary, marginBottom: Spacing.xs, marginTop: Spacing.sm },
  input: {
    backgroundColor: Colors.inputBg, borderRadius: Radius.md,
    paddingVertical: scale(12), paddingHorizontal: scale(14),
    fontSize: scale(14), color: Colors.textPrimary, marginBottom: Spacing.sm,
  },
  passwordRow: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.sm },
  eyeBtn: { position: 'absolute', right: scale(12) },
  eyeIcon: { fontSize: scale(18) },
  forgotLink: { color: Colors.accent, fontSize: scale(12), textAlign: 'right', fontWeight: '500', marginBottom: Spacing.sm },
  errorText: { color: Colors.error, fontSize: scale(12), textAlign: 'center', marginBottom: Spacing.sm },
  loginBtn: {
    backgroundColor: Colors.accent, borderRadius: Radius.full,
    paddingVertical: scale(13), alignItems: 'center', marginTop: Spacing.xs,
  },
  loginBtnText: { color: Colors.white, fontSize: scale(15), fontWeight: '700' },
  divider: { flexDirection: 'row', alignItems: 'center', marginVertical: Spacing.md },
  dividerLine: { flex: 1, height: 1, backgroundColor: Colors.border },
  dividerText: { marginHorizontal: Spacing.sm, color: Colors.textMuted, fontSize: scale(12) },
  googleBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.full,
    paddingVertical: scale(11), gap: scale(8),
  },
  googleG: { fontSize: scale(18), fontWeight: '700', color: '#4285F4' },
  googleText: { fontSize: scale(13), fontWeight: '500', color: Colors.textPrimary },
  signupRow: { flexDirection: 'row', justifyContent: 'center', marginTop: Spacing.lg },
  signupText: { fontSize: scale(12), color: Colors.textSecondary },
  signupLink: { fontSize: scale(12), fontWeight: '700', color: Colors.accent },
  devBtn: {
    marginTop: Spacing.lg, paddingVertical: scale(10), backgroundColor: Colors.inputBg,
    borderRadius: Radius.sm, alignItems: 'center', borderWidth: 1, borderColor: Colors.border, borderStyle: 'dashed',
  },
  devText: { color: Colors.textMuted, fontSize: scale(12), fontWeight: '600' },
  footer: {
    textAlign: 'center', fontSize: scale(14), fontWeight: '800', color: Colors.primary,
    marginTop: Spacing.xl, marginBottom: Spacing.lg, letterSpacing: 1,
  },
});
