import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Loading data...',
  size = 'md',
}) => {
  const iconSize = size === 'sm' ? 16 : size === 'lg' ? 32 : 22;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '36px 20px',
        color: '#94a3b8',
        gap: '12px',
      }}
    >
      <RefreshCw
        size={iconSize}
        style={{
          animation: 'spin 1s linear infinite',
          color: 'var(--primary-400)',
        }}
      />
      {message && <span style={{ fontSize: '13px', color: '#94a3b8' }}>{message}</span>}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

interface ErrorAlertProps {
  title?: string;
  message: string;
  code?: string;
  correlationId?: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'Request Failed',
  message,
  code,
  correlationId,
  onRetry,
}) => {
  return (
    <div
      style={{
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        border: '1px solid rgba(239, 68, 68, 0.3)',
        borderRadius: '8px',
        padding: '14px 18px',
        display: 'flex',
        gap: '12px',
        alignItems: 'flex-start',
        color: '#f87171',
      }}
    >
      <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '2px' }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '2px' }}>
          {title} {code && <span style={{ opacity: 0.75, fontWeight: 400 }}>({code})</span>}
        </div>
        <div style={{ fontSize: '13px', color: '#fca5a5', lineHeight: 1.4 }}>{message}</div>
        {correlationId && (
          <div
            style={{
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              marginTop: '6px',
              color: '#f87171',
              opacity: 0.8,
            }}
          >
            Correlation ID: {correlationId}
          </div>
        )}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rf-btn rf-btn-secondary rf-btn-sm"
          style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: '#fca5a5' }}
        >
          Retry
        </button>
      )}
    </div>
  );
};
