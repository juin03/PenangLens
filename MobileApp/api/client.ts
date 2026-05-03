import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ──────────────────────────────── Config ────────────────────────────────

const getBaseUrl = () => {
  if (__DEV__) {
    const LAN_IP = '192.168.0.192'; //ipconfig | findstr "IPv4"
    if (Platform.OS === 'web') return 'http://localhost';
    return `http://${LAN_IP}`;
  }
  return 'https://your-production-url.com';
};

const BASE = getBaseUrl();
export const API_BASE_URL = `${BASE}/api/v1`;   // Next.js BFF proxy to Agent
const AUTH_URL = `${BASE}/api/auth`;             // BFF auth
const DATA_URL = `${BASE}/api`;                  // BFF data

const getVisionUrl = () => {
  // Proxied through Next.js (port 3000) to avoid port 8001 being blocked on university WiFi
  return BASE;
};
export const VISION_BASE_URL = getVisionUrl();

// ──────────────────────────────── Token Management ────────────────────

const TOKEN_KEY = 'penanglens_token';
const USER_KEY = 'penanglens_user';

export async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await AsyncStorage.multiRemove([TOKEN_KEY, USER_KEY]);
}

export async function getStoredUser(): Promise<any | null> {
  const raw = await AsyncStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ──────────────────────────────── Types ────────────────────────────────

export interface GenerateRequest {
  description: string;
  interests: string[];
  start_time: string;
  end_time: string;
  start_location: string;
  travel_mode: 'walking' | 'driving' | 'transit';
  start_date?: string;   // optional: YYYY-MM-DD for multi-day plans
  end_date?: string;     // optional: YYYY-MM-DD for multi-day plans
}

export interface ChatRequest {
  message: string;
  thread_id?: string;
}

export interface AuthResponse {
  user: { id: string; email: string; name: string; role?: string; interests?: string[] };
  token: string;
}

// ──────────────────────────────── Auth API ────────────────────────────

export async function registerUser(email: string, password: string, name?: string, interests?: string[]): Promise<AuthResponse> {
  const res = await fetch(`${AUTH_URL}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name, interests }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Registration failed');
  }
  const data: AuthResponse = await res.json();
  await setToken(data.token);
  await AsyncStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data;
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${AUTH_URL}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || 'Login failed');
  }
  const data: AuthResponse = await res.json();
  await setToken(data.token);
  await AsyncStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data;
}

export async function getProfile() {
  const headers = await authHeaders();
  const res = await fetch(`${AUTH_URL}/me`, { headers });
  if (!res.ok) throw new Error('Failed to fetch profile');
  return res.json();
}

export async function updateProfile(data: { name?: string; interests?: string[] }) {
  const headers = await authHeaders();
  const res = await fetch(`${AUTH_URL}/me`, {
    method: 'PATCH', headers,
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update profile');
  return res.json();
}

export async function logout() {
  await clearToken();
}

export async function forgotPassword(email: string): Promise<{ success: boolean; resetToken?: string }> {
  const res = await fetch(`${AUTH_URL}/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error('Request failed');
  return res.json();
}

export async function resetPassword(token: string, password: string): Promise<void> {
  const res = await fetch(`${AUTH_URL}/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || 'Reset failed');
  }
}

// ──────────────────────────────── Itinerary API ────────────────────────

export async function updateItinerary(id: string, data: { generatedNarrative?: string; name?: string; totalDuration?: number }) {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/itineraries/${id}`, {
    method: 'PATCH', headers, body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update itinerary');
  return res.json();
}

export async function saveItinerary(data: {
  name: string; originalPrompt?: string; generatedNarrative?: string; totalDuration?: number; threadId?: string;
  stops?: { stopOrder: number; travelTimeMin?: number; name?: string }[];
}) {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/itineraries`, {
    method: 'POST', headers, body: JSON.stringify(data),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to save itinerary');
  }
  return res.json();
}

export async function getItineraries() {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/itineraries`, { headers });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to fetch itineraries');
  }
  return res.json();
}

export async function deleteItinerary(id: string) {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/itineraries/${id}`, { method: 'DELETE', headers });
  if (!res.ok) {
    if (res.status === 401) throw new Error('Unauthorized');
    throw new Error('Failed to delete itinerary');
  }
  return res.json();
}


export async function saveChatMessages(itineraryId: string, messages: { role: string; content: string }[]) {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/itineraries/${itineraryId}/chat`, {
    method: 'POST', headers, body: JSON.stringify({ messages }),
  });
  if (!res.ok) throw new Error('Failed to save chat');
  return res.json();
}
// ──────────────────────────────── Scan History API ────────────────────

export async function saveScanResult(data: {
  userImageUrl?: string; userLatitude?: number; userLongitude?: number;
  annotatedImageBase64?: string; aiDetails?: any; poiId?: string;
}) {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/scans`, {
    method: 'POST', headers, body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`Failed to save scan (${res.status}): ${errText}`);
  }
  return res.json();
}

export async function getScanHistory() {
  const headers = await authHeaders();
  const res = await fetch(`${DATA_URL}/scans`, { headers });
  if (!res.ok) throw new Error('Failed to fetch scan history');
  return res.json();
}

// ──────────────────────────────── Agent Proxy API ────────────────────

export const generateItinerary = async (request: GenerateRequest) => {
  const res = await fetch(`${API_BASE_URL}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Generate failed (${res.status}): ${errText}`);
  }
  return res.json();
};

export const chatWithAgent = async (request: ChatRequest) => {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error(`Chat failed (${res.status})`);
  return res.json();
};

export const scanLandmark = async (imageUri: string) => {
  const formData = new FormData();
  formData.append('image', { uri: imageUri, type: 'image/jpeg', name: 'scan.jpg' } as any);
  const res = await fetch(`${VISION_BASE_URL}/api/vision/pipeline`, {
    method: 'POST', body: formData,
  });
  if (!res.ok) throw new Error(`Scan failed (${res.status})`);
  return res.json();
};

export const getUsageStats = async () => {
  const res = await fetch(`${API_BASE_URL}/usage`);
  if (!res.ok) throw new Error(`Usage fetch failed (${res.status})`);
  return res.json();
};
