'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

const navItems = [
  { href: '/admin/spots', label: 'Content', icon: '🏛️' },
  { href: '/admin/map', label: 'Map', icon: '🗺️' },
  { href: '/admin/itineraries', label: 'Itinerary Feedback', icon: '🗓️' },
  { href: '/admin/recognition', label: 'Scan Feedback', icon: '🔍' },
  { href: '/admin/chat-feedback', label: 'Chat Feedback', icon: '💬' },
  { href: '/admin/users', label: 'Users', icon: '👥' },
  { href: '/admin/system', label: 'System', icon: '⚙️' },
];

const footerItems = [
  { href: '/admin/help', label: 'Help', icon: '❓' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    router.push('/admin/login');
  };

  return (
    <aside className="admin-sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-title">🗺️ PenangLens</div>
        <div className="sidebar-logo-sub">Admin Panel</div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-link ${isActive ? 'active' : ''}`}
            >
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        {footerItems.map((item) => (
          <Link key={item.href} href={item.href} className="sidebar-link">
            <span style={{ fontSize: 16 }}>{item.icon}</span>
            {item.label}
          </Link>
        ))}
        <button
          onClick={handleLogout}
          className="sidebar-link"
          style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
        >
          <span style={{ fontSize: 16 }}>🚪</span>
          Logout
        </button>
      </div>
    </aside>
  );
}
