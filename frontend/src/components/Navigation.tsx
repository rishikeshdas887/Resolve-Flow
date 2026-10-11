import React from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  ExternalLink,
  History,
  LayoutDashboard,
  LogOut,
  Shield,
  Ticket,
  User as UserIcon,
} from 'lucide-react';
import type { User } from '../types';

export type NavTab = 'dashboard' | 'tickets' | 'approvals' | 'knowledge' | 'evals' | 'audit';

interface NavigationProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  currentUser: User | null;
  onLogout: () => void;
  pendingApprovalsCount?: number;
}

export const Sidebar: React.FC<NavigationProps> = ({
  currentTab,
  onSelectTab,
  currentUser,
  pendingApprovalsCount = 0,
}) => {
  const navItems: Array<{
    id: NavTab;
    label: string;
    icon: React.ReactNode;
    badge?: number;
    badgeVariant?: 'amber' | 'indigo';
    adminOnly?: boolean;
  }> = [
    {
      id: 'dashboard',
      label: 'Operations Board',
      icon: <LayoutDashboard size={18} />,
    },
    {
      id: 'tickets',
      label: 'Ticket Queue',
      icon: <Ticket size={18} />,
    },
    {
      id: 'approvals',
      label: 'Approval Queue',
      icon: <Shield size={18} />,
      badge: pendingApprovalsCount,
      badgeVariant: 'amber',
      adminOnly: true,
    },
    {
      id: 'knowledge',
      label: 'Knowledge Base',
      icon: <BookOpen size={18} />,
    },
    {
      id: 'evals',
      label: 'Model Evaluations',
      icon: <Activity size={18} />,
      adminOnly: true,
    },
    {
      id: 'audit',
      label: 'Audit & Telemetry',
      icon: <History size={18} />,
    },
  ];

  return (
    <aside className="rf-sidebar">
      {/* Brand Header */}
      <div
        style={{
          padding: '20px 22px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: '16px',
            boxShadow: '0 0 12px rgba(99, 102, 241, 0.4)',
          }}
        >
          RF
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '-0.02em', color: '#f8fafc' }}>
            ResolveFlow
          </div>
          <div
            style={{
              fontSize: '11px',
              color: '#94a3b8',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>AI Operations</span>
            <span
              style={{
                fontSize: '9px',
                padding: '1px 5px',
                backgroundColor: 'rgba(99, 102, 241, 0.15)',
                color: 'var(--primary-400)',
                borderRadius: '4px',
                fontWeight: 600,
              }}
            >
              v1.0
            </span>
          </div>
        </div>
      </div>

      {/* Nav List */}
      <nav style={{ padding: '16px 12px', flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div
          style={{
            fontSize: '11px',
            fontWeight: 600,
            color: '#64748b',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            padding: '4px 12px 8px',
          }}
        >
          Operations Menu
        </div>
        {navItems.map((item) => {
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '9px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? '#ffffff' : '#94a3b8',
                backgroundColor: isActive ? 'var(--color-surface-hover)' : 'transparent',
                border: isActive ? '1px solid var(--border-default)' : '1px solid transparent',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all var(--transition-fast)',
                width: '100%',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ color: isActive ? 'var(--primary-400)' : '#64748b' }}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span
                  style={{
                    backgroundColor:
                      item.badgeVariant === 'amber'
                        ? 'rgba(251, 191, 36, 0.2)'
                        : 'rgba(99, 102, 241, 0.2)',
                    color: item.badgeVariant === 'amber' ? '#fbbf24' : 'var(--primary-400)',
                    border:
                      item.badgeVariant === 'amber'
                        ? '1px solid rgba(251, 191, 36, 0.4)'
                        : '1px solid rgba(99, 102, 241, 0.4)',
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '1px 7px',
                    borderRadius: '999px',
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Info & API Link */}
      <div
        style={{
          padding: '16px',
          borderTop: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--color-surface-base)',
        }}
      >
        <div
          style={{
            backgroundColor: 'var(--color-surface-raised)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '10px 12px',
            marginBottom: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '11px', color: '#64748b' }}>Role Scope</span>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: currentUser?.role === 'admin' ? '#34d399' : '#38bdf8',
              }}
            >
              {currentUser?.role || 'Guest'}
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
            {currentUser?.role === 'admin'
              ? 'Full policy & approval execution'
              : 'Agent operations & ticket triage'}
          </div>
        </div>

        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '12px',
            color: '#94a3b8',
            textDecoration: 'none',
            padding: '6px 4px',
          }}
        >
          <span>OpenAPI Docs</span>
          <ExternalLink size={13} />
        </a>
      </div>
    </aside>
  );
};

export const Navbar: React.FC<NavigationProps> = ({
  currentUser,
  onLogout,
  pendingApprovalsCount = 0,
}) => {
  return (
    <header className="rf-header">
      {/* System Status Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'rgba(52, 211, 153, 0.1)',
            border: '1px solid rgba(52, 211, 153, 0.25)',
            padding: '4px 12px',
            borderRadius: '999px',
            fontSize: '12px',
            color: '#34d399',
            fontWeight: 500,
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: '#34d399',
              boxShadow: '0 0 8px #34d399',
            }}
          />
          Deterministic Core Active • Worker Connected
        </div>

        {pendingApprovalsCount > 0 && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'rgba(251, 191, 36, 0.12)',
              border: '1px solid rgba(251, 191, 36, 0.3)',
              padding: '4px 12px',
              borderRadius: '999px',
              fontSize: '12px',
              color: '#fbbf24',
              fontWeight: 600,
            }}
          >
            <AlertTriangle size={13} />
            {pendingApprovalsCount} Action{pendingApprovalsCount > 1 ? 's' : ''} Awaiting Review
          </div>
        )}
      </div>

      {/* User Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {currentUser ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                {currentUser.full_name || currentUser.email}
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>
                {currentUser.email}
              </div>
            </div>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-surface-hover)',
                border: '1px solid var(--border-default)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--primary-400)',
              }}
            >
              <UserIcon size={17} />
            </div>
            <button
              onClick={onLogout}
              className="rf-btn rf-btn-ghost rf-btn-sm"
              title="Sign Out"
              style={{ color: '#94a3b8' }}
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>Not signed in</div>
        )}
      </div>
    </header>
  );
};
