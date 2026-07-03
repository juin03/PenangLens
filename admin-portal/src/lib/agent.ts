/**
 * Shared config for calling the Agent microservice.
 *
 * When AGENT_INTERNAL_KEY is set (must match the Agent's env var), every request
 * carries the X-Internal-Key header so the Agent can reject direct internet traffic.
 */
export const AGENT_BASE_URL =
  process.env.AGENT_URL || process.env.AGENT_BASE_URL || 'http://127.0.0.1:8000';

export function agentHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...extra };
  if (process.env.AGENT_INTERNAL_KEY) {
    headers['X-Internal-Key'] = process.env.AGENT_INTERNAL_KEY;
  }
  return headers;
}
