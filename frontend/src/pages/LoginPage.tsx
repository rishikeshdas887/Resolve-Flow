import React, { useState } from 'react';
import { KeyRound, Lock, Mail, ShieldAlert, Sparkles } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { User } from '../types';

interface LoginPageProps {
  onLoginSuccess: (user: User) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('AdminPass123!');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await api.login(email, password);
      onLoginSuccess(res.user);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to authenticate with backend');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (role: 'admin' | 'agent') => {
    if (role === 'admin') {
      setEmail('admin@example.com');
      setPassword('AdminPass123!');
    } else {
      setEmail('agent@example.com');
      setPassword('AgentPass123!');
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-canvas)',
        padding: '24px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle background ambient glow */}
      <div
        style={{
          position: 'absolute',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, transparent 70%)',
          top: '20%',
          left: '50%',
          transform: 'translateX(-50%)',
          pointerEvents: 'none',
        }}
      />

      <div
        className="rf-card"
        style={{
          width: '100%',
          maxWidth: '440px',
          backgroundColor: 'var(--color-surface-base)',
          border: '1px solid var(--border-default)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-panel)',
          padding: '36px 32px',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: 800,
              fontSize: '22px',
              boxShadow: '0 0 20px rgba(99, 102, 241, 0.5)',
              marginBottom: '16px',
            }}
          >
            RF
          </div>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#f8fafc',
              marginBottom: '6px',
            }}
          >
            ResolveFlow Operations
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Evidence-grounded autonomous support platform
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '8px',
              padding: '12px 14px',
              fontSize: '13px',
              color: '#f87171',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
            }}
          >
            <ShieldAlert size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#cbd5e1',
                marginBottom: '6px',
              }}
            >
              Email Address
            </label>
            <div style={{ position: 'relative' }}>
              <Mail
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#64748b',
                }}
              />
              <input
                type="email"
                className="rf-input"
                style={{ paddingLeft: '38px' }}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>
          </div>

          <div>
            <label
              style={{
                display: 'block',
                fontSize: '12px',
                fontWeight: 600,
                color: '#cbd5e1',
                marginBottom: '6px',
              }}
            >
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock
                size={16}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#64748b',
                }}
              />
              <input
                type="password"
                className="rf-input"
                style={{ paddingLeft: '38px' }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="rf-btn rf-btn-primary"
            style={{ width: '100%', padding: '10px', fontSize: '14px', marginTop: '6px' }}
            disabled={loading}
          >
            {loading ? 'Authenticating...' : 'Sign In to Operations'}
          </button>
        </form>

        {/* Quick Fill Demo Credentials */}
        <div
          style={{
            marginTop: '28px',
            paddingTop: '20px',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#64748b',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: '10px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Sparkles size={12} color="var(--primary-400)" />
            <span>Local Demo Profiles</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <button
              type="button"
              onClick={() => handleQuickFill('admin')}
              className="rf-btn rf-btn-secondary rf-btn-sm"
              style={{ fontSize: '12px', justifyContent: 'flex-start' }}
            >
              <KeyRound size={13} style={{ color: 'var(--primary-400)' }} />
              <span>Admin Profile</span>
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('agent')}
              className="rf-btn rf-btn-secondary rf-btn-sm"
              style={{ fontSize: '12px', justifyContent: 'flex-start' }}
            >
              <KeyRound size={13} style={{ color: '#38bdf8' }} />
              <span>Agent Profile</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
