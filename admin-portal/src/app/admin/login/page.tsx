'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Login failed');
      if (data.user?.role !== 'admin') throw new Error('Access denied. Admin account required.');
      localStorage.setItem('admin_token', data.token);
      // Set cookie so the Next.js middleware can protect routes server-side
      document.cookie = `admin_token=${data.token}; path=/; SameSite=Lax`;
      router.replace('/admin/spots');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh', background: 'linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, sans-serif',
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: '40px 36px', width: 380,
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🗺️</div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: '#111827', margin: 0 }}>PenangLens</h1>
          <p style={{ fontSize: 13, color: '#6b7280', margin: '4px 0 0' }}>Admin Portal</p>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Email address
            </label>
            <input
              type="email" required autoFocus
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="admin@penanglens.com"
              style={{
                width: '100%', padding: '10px 12px', border: '1px solid #d1d5db',
                borderRadius: 8, fontSize: 14, color: '#111827', outline: 'none',
                boxSizing: 'border-box', fontFamily: 'inherit', background: '#fff',
              }}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password" required
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: '100%', padding: '10px 12px', border: '1px solid #d1d5db',
                borderRadius: 8, fontSize: 14, color: '#111827', outline: 'none',
                boxSizing: 'border-box', fontFamily: 'inherit', background: '#fff',
              }}
            />
          </div>

          {error && (
            <div style={{
              background: '#fef2f2', border: '1px solid #fca5a5', color: '#dc2626',
              borderRadius: 8, padding: '10px 14px', fontSize: 13, marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              width: '100%', padding: '11px', background: loading ? '#93c5fd' : '#2563eb',
              color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
              transition: 'background 0.15s',
            }}
          >
            {loading ? 'Signing in...' : 'Sign in to Admin Panel'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 12, color: '#9ca3af', marginTop: 20, marginBottom: 0 }}>
          Only admin accounts can access this portal.
        </p>
      </div>
    </div>
  );
}
