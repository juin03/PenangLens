import { API_BASE_URL } from './client';
import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_KEY = 'penanglens_token';

async function getAuthHeaders() {
  const token = await AsyncStorage.getItem(TOKEN_KEY);
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface StreamUpdate {
  type: 'status' | 'chunk' | 'complete' | 'error';
  message?: string;
  content?: string;
  data?: any;
}

/**
 * Stream chat responses with real-time updates
 */
export async function* streamChat(
  message: string,
  threadId?: string,
  spotId?: string,
  context?: string
): AsyncGenerator<StreamUpdate> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      message,
      thread_id: threadId,
      spot_id: spotId,
      context,
    }),
  });

  if (!response.ok) {
    throw new Error('Chat stream failed');
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          
          if (data.type === 'token') {
            yield { type: 'chunk', content: data.content };
          } else if (data.type === 'complete') {
            yield { type: 'complete', data: data };
          } else if (data.type === 'error') {
            yield { type: 'error', message: data.message };
          }
        } catch (e) {
          // Skip invalid JSON
        }
      }
    }
  }
}

/**
 * Stream itinerary generation with optimization updates
 */
export async function* streamItinerary(request: {
  description: string;
  interests: string[];
  start_time: string;
  end_time: string;
  start_location?: string;
  travel_mode?: string;
  start_date?: string;
  end_date?: string;
}): AsyncGenerator<StreamUpdate> {
  const headers = await getAuthHeaders();
  
  const response = await fetch(`${API_BASE_URL}/generate/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error('Itinerary stream failed');
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          
          if (data.type === 'status') {
            yield { type: 'status', message: data.message };
          } else if (data.type === 'complete') {
            yield { type: 'complete', data: data.data };
          } else if (data.type === 'error') {
            yield { type: 'error', message: data.message };
          }
        } catch (e) {
          // Skip invalid JSON
        }
      }
    }
  }
}
