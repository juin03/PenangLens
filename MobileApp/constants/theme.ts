import { Dimensions } from 'react-native';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Moderate scaling: scale barely (factor 0.2) so we mostly rely on RN's native density-independent pixels
// but still give a tiny bit of responsiveness across weird aspect ratios.
export const scale = (size: number) => {
  const scaled = (SCREEN_WIDTH / 375) * size;
  return size + (scaled - size) * 0.2;
};

export const verticalScale = (size: number) => {
  const scaled = (SCREEN_HEIGHT / 812) * size;
  return size + (scaled - size) * 0.2;
};

export const Colors = {
  // Primary palette (dark teal / navy from Figma)
  primary: '#1B3A4B',
  primaryDark: '#0F2634',
  primaryLight: '#2D5F73',
  primaryMid: '#2A4F63',   // mid-tone teal — use instead of any hardcoded purple

  // Accent (golden yellow from Figma buttons)
  accent: '#E8A838',
  accentDark: '#C88B20',
  accentLight: 'rgba(232,168,56,0.15)',

  // Status
  success: '#10B981',
  error: '#EF4444',
  warning: '#F59E0B',

  // Neutrals
  white: '#FFFFFF',
  background: '#F5F6F8',
  card: '#FFFFFF',
  border: '#E5E7EB',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  inputBg: '#F3F4F6',

  // Tab bar
  tabBar: '#1B3A4B',
  tabActive: '#E8A838',
  tabInactive: '#94A3B8',

  // Overlay
  overlay: 'rgba(0,0,0,0.5)',

  // Semantic aliases
  headerSubtitle: 'rgba(255,255,255,0.7)',   // secondary text on dark primary headers
};

export const Fonts = {
  h1: { fontSize: scale(26), fontWeight: '800' as const },
  h2: { fontSize: scale(20), fontWeight: '700' as const },
  h3: { fontSize: scale(16), fontWeight: '600' as const },
  body: { fontSize: scale(14), fontWeight: '400' as const },
  caption: { fontSize: scale(12), fontWeight: '400' as const },
  small: { fontSize: scale(11), fontWeight: '400' as const },
};

export const Spacing = {
  xs: scale(4),
  sm: scale(8),
  md: scale(14),
  lg: scale(20),
  xl: scale(28),
  xxl: scale(40),
};

export const Radius = {
  sm: scale(6),
  md: scale(10),
  lg: scale(14),
  xl: scale(20),
  full: 999,
};

/** Reusable shadow presets — spread into StyleSheet: { ...Shadow.md } */
export const Shadow = {
  sm: {
    shadowColor: '#000' as const,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: '#000' as const,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 4,
  },
  lg: {
    shadowColor: '#000' as const,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 10,
    elevation: 6,
  },
};

export { SCREEN_WIDTH, SCREEN_HEIGHT };
