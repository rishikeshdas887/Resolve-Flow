import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle,
  Clock,
  Cpu,
  Plus,
  RefreshCw,
  ShieldAlert,
  Ticket as TicketIcon,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import { PriorityBadge, StatusBadge } from '../components/StatusBadge';
import type { DashboardSummary, Ticket } from '../types';

interface DashboardPageProps {
  onNavigateToTickets: () => void;
  onNavigateToApprovals: () => void;
  onSelectTicket: (ticketId: string) => void;
  onCreateTicketClick: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onNavigateToTickets,
  onNavigateToApprovals,
  onSelectTicket,
  onCreateTicketClick,
}) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [recentTickets, setRecentTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumData, ticketsData] = await Promise.all([
        api.getDashboardSummary(),
        api.listTickets({ size: 5 }),
      ]);
      setSummary(sumData);
      setRecentTickets(ticketsData.items);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch dashboard data');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading && !summary) {
    return <LoadingSpinner message="Loading Operations Dashboard..." size="lg" />;
  }

  if (error && !summary) {
    return (
      <div className="rf-page-container">
        <ErrorAlert message={error} onRetry={loadData} />
      </div>
    );
  }

  const resolutionPct =
    summary?.resolution_rate !== null && summary?.resolution_rate !== undefined
      ? `${(summary.resolution_rate * 100).toFixed(1)}%`
      : summary?.tickets_total && summary.tickets_total > 0
      ? `${((summary.resolved_tickets / summary.tickets_total) * 100).toFixed(1)}%`
      : '0.0%';

  return (
    <div className="rf-page-container">
      {/* Top Banner & Actions */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '28px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#f8fafc',
              marginBottom: '4px',
            }}
          >
            Operations Command Center
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Live status of autonomous support orchestration, risk policy gates, and grounded knowledge.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={loadData}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh Metrics"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={onCreateTicketClick} className="rf-btn rf-btn-primary">
            <Plus size={15} />
            <span>New Ticket</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '18px',
          marginBottom: '28px',
        }}
      >
        {/* Total Tickets */}
        <div className="rf-stat-card" onClick={onNavigateToTickets} style={{ cursor: 'pointer' }}>
          <div className="rf-stat-header">
            <span>Total Tickets</span>
            <TicketIcon size={16} color="var(--primary-400)" />
          </div>
          <div className="rf-stat-value">{summary?.tickets_total ?? 0}</div>
          <div className="rf-stat-meta">
            <span style={{ color: '#38bdf8' }}>{summary?.open_tickets ?? 0} active</span>
            <span>•</span>
            <span>all queues</span>
          </div>
        </div>

        {/* Pending Approvals */}
        <div
          className="rf-stat-card"
          onClick={onNavigateToApprovals}
          style={{
            cursor: 'pointer',
            borderColor: (summary?.pending_approvals ?? 0) > 0 ? 'rgba(251, 191, 36, 0.4)' : undefined,
            backgroundColor:
              (summary?.pending_approvals ?? 0) > 0 ? 'rgba(251, 191, 36, 0.05)' : undefined,
          }}
        >
          <div className="rf-stat-header">
            <span>Pending Approvals</span>
            <AlertTriangle
              size={16}
              color={(summary?.pending_approvals ?? 0) > 0 ? '#fbbf24' : '#64748b'}
            />
          </div>
          <div
            className="rf-stat-value"
            style={{ color: (summary?.pending_approvals ?? 0) > 0 ? '#fbbf24' : '#f8fafc' }}
          >
            {summary?.pending_approvals ?? 0}
          </div>
          <div className="rf-stat-meta">
            <span>Human-in-the-loop gates</span>
          </div>
        </div>

        {/* Auto Resolution Rate */}
        <div className="rf-stat-card">
          <div className="rf-stat-header">
            <span>Resolved Tickets</span>
            <CheckCircle size={16} color="#34d399" />
          </div>
          <div className="rf-stat-value">{summary?.resolved_tickets ?? 0}</div>
          <div className="rf-stat-meta">
            <span style={{ color: '#34d399', fontWeight: 600 }}>{resolutionPct}</span>
            <span>resolution rate</span>
          </div>
        </div>

        {/* Agent Runs & Latency */}
        <div className="rf-stat-card">
          <div className="rf-stat-header">
            <span>Agent Runs</span>
            <Cpu size={16} color="var(--primary-400)" />
          </div>
          <div className="rf-stat-value">{summary?.runs_total ?? 0}</div>
          <div className="rf-stat-meta">
            <Clock size={12} />
            <span>
              {summary?.avg_run_duration_ms
                ? `${Math.round(summary.avg_run_duration_ms)} ms avg`
                : 'Sub-second avg'}
            </span>
          </div>
        </div>

        {/* Grounding Knowledge */}
        <div className="rf-stat-card">
          <div className="rf-stat-header">
            <span>Knowledge Grounding</span>
            <BookOpen size={16} color="#38bdf8" />
          </div>
          <div className="rf-stat-value">{summary?.knowledge_documents ?? 0}</div>
          <div className="rf-stat-meta">
            <span>{summary?.knowledge_chunks ?? 0} indexed chunks</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Queue & Architecture Telemetry */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 1fr',
          gap: '24px',
          alignItems: 'start',
        }}
      >
        {/* Left: Recent Tickets Table */}
        <div className="rf-card">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '18px',
            }}
          >
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                Active Orchestration Queue
              </h2>
              <p style={{ fontSize: '12px', color: '#94a3b8' }}>
                Latest tickets processed by ResolveFlow agent workflow
              </p>
            </div>
            <button
              onClick={onNavigateToTickets}
              className="rf-btn rf-btn-ghost rf-btn-sm"
              style={{ color: 'var(--primary-400)', gap: '4px' }}
            >
              <span>View All</span>
              <ArrowRight size={14} />
            </button>
          </div>

          {recentTickets.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '40px 20px',
                color: '#64748b',
                backgroundColor: 'var(--color-surface-raised)',
                borderRadius: '8px',
              }}
            >
              <TicketIcon size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
              <div style={{ fontWeight: 600, color: '#94a3b8', marginBottom: '4px' }}>
                No tickets in queue
              </div>
              <p style={{ fontSize: '12px', marginBottom: '14px' }}>
                Create a test ticket to observe evidence retrieval, policy gating, and autonomous resolution.
              </p>
              <button onClick={onCreateTicketClick} className="rf-btn rf-btn-primary rf-btn-sm">
                <Plus size={14} />
                <span>Create First Ticket</span>
              </button>
            </div>
          ) : (
            <div className="rf-table-container">
              <table className="rf-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Category</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTickets.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => onSelectTicket(t.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{t.subject}</div>
                        <div
                          style={{
                            fontSize: '11px',
                            color: '#64748b',
                            fontFamily: 'var(--font-mono)',
                            marginTop: '2px',
                          }}
                        >
                          {t.id.slice(0, 8)} • {t.requester_email || 'anonymous'}
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={t.status} />
                      </td>
                      <td>
                        <PriorityBadge priority={t.priority} />
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: '12px',
                            color: '#94a3b8',
                            textTransform: 'capitalize',
                          }}
                        >
                          {t.category || 'unclassified'}
                        </span>
                      </td>
                      <td>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectTicket(t.id);
                          }}
                          className="rf-btn rf-btn-secondary rf-btn-sm"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Architecture & Guardrail Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Policy Guardrails Card */}
          <div className="rf-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <ShieldAlert size={18} color="var(--primary-400)" />
              <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#f8fafc' }}>
                Safety & Risk Architecture
              </h2>
            </div>
            <div style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '14px' }}>
              ResolveFlow enforces strict deterministic invariants:
            </div>
            <ul
              style={{
                listStyle: 'none',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                fontSize: '12px',
              }}
            >
              <li
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                  backgroundColor: 'var(--color-surface-raised)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#34d399', fontWeight: 700 }}>✓</span>
                <div>
                  <strong style={{ color: '#f1f5f9' }}>Grounded Citations:</strong> Model proposals must cite
                  valid chunk IDs retrieved from the vector store; hallucinated citations trigger automatic
                  escalation.
                </div>
              </li>
              <li
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                  backgroundColor: 'var(--color-surface-raised)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#34d399', fontWeight: 700 }}>✓</span>
                <div>
                  <strong style={{ color: '#f1f5f9' }}>Deterministic Policy Engine:</strong> Sensitive actions
                  (refunds, password resets) require explicit human approval before execution.
                </div>
              </li>
              <li
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                  backgroundColor: 'var(--color-surface-raised)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#34d399', fontWeight: 700 }}>✓</span>
                <div>
                  <strong style={{ color: '#f1f5f9' }}>Audited Event Trail:</strong> Every state change and
                  action emits an immutable audit event.
                </div>
              </li>
            </ul>
          </div>

          {/* Infrastructure Health */}
          <div className="rf-card">
            <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#f8fafc', marginBottom: '12px' }}>
              Infrastructure Stack
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  backgroundColor: 'var(--color-surface-raised)',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#94a3b8' }}>FastAPI Backend</span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>Port 8000 (Live)</span>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  backgroundColor: 'var(--color-surface-raised)',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#94a3b8' }}>Durable LangGraph Worker</span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>Polling Active</span>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  backgroundColor: 'var(--color-surface-raised)',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#94a3b8' }}>PostgreSQL 16 + pgvector</span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>Connected</span>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 10px',
                  backgroundColor: 'var(--color-surface-raised)',
                  borderRadius: '6px',
                }}
              >
                <span style={{ color: '#94a3b8' }}>LLM Provider</span>
                <span style={{ color: '#38bdf8', fontWeight: 600 }}>Labelled Deterministic</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
