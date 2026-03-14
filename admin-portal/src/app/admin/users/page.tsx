'use client';

import { useEffect, useState } from 'react';

interface User { id: string; email: string; name?: string; role: string; createdAt: string; }

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => { fetchUsers(); }, []);
  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/admin/users');
      const data = await res.json();
      setUsers(data.users || []);
    } catch { setUsers([]); }
    setLoading(false);
  };

  const updateRole = async (id: string, role: string) => {
    await fetch(`/api/admin/users/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    fetchUsers();
  };

  const filtered = users.filter(u =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.name || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="page-sub">Manage registered users and their roles.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-label">Total Users</div>
          <div className="stat-value">{loading ? '...' : users.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Admins</div>
          <div className="stat-value">{loading ? '...' : users.filter(u => u.role === 'admin').length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Regular Users</div>
          <div className="stat-value">{loading ? '...' : users.filter(u => u.role === 'user').length}</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ padding: '14px 20px' }}>
          <input className="form-input" placeholder="Search by name or email…" style={{ width: 280 }}
            value={search} onChange={e => setSearch(e.target.value)} />
        </div>
      </div>

      <div className="card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>USER</th>
              <th>EMAIL</th>
              <th>ROLE</th>
              <th>JOINED</th>
              <th style={{ textAlign: 'right' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#9ca3af', padding: 40 }}>No users found.</td></tr>
            ) : filtered.map(user => (
              <tr key={user.id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#e0e7ff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 14, color: '#3730a3' }}>
                      {(user.name || user.email).charAt(0).toUpperCase()}
                    </div>
                    <span style={{ fontWeight: 500 }}>{user.name || '—'}</span>
                  </div>
                </td>
                <td style={{ color: '#6b7280', fontSize: 13 }}>{user.email}</td>
                <td>
                  <span className={`badge ${user.role === 'admin' ? 'badge-new' : 'badge-draft'}`}>
                    {user.role === 'admin' ? '🛡 Admin' : '👤 User'}
                  </span>
                </td>
                <td style={{ color: '#6b7280', fontSize: 13 }}>
                  {new Date(user.createdAt).toLocaleDateString('en-MY', { year: 'numeric', month: 'short', day: 'numeric' })}
                </td>
                <td style={{ textAlign: 'right' }}>
                  {user.role === 'user' ? (
                    <button className="btn btn-outline btn-sm" onClick={() => updateRole(user.id, 'admin')}>
                      Make Admin
                    </button>
                  ) : (
                    <button className="btn btn-danger btn-sm" onClick={() => updateRole(user.id, 'user')}>
                      Revoke Admin
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
