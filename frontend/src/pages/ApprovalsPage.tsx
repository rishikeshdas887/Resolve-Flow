import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  ExternalLink,
  Info,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import { StatusBadge } from '../components/StatusBadge';
import type { ApprovalRequest, User } from '../types';

interface ApprovalsPageProps {
  currentUser: User | null;
  onSelectTicket: (ticketId: string) => void;
}

export const ApprovalsPage: React.FC<ApprovalsPageProps> = ({
  currentUser,
  onSelectTicket,
}) => {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRequest | null>(null);
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | ''>(
    'pending'
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Decision inputs
  const [evidence, setEvidence] = useState<any[]>([]);
  const [decisionNote, setDecisionNote] = useState('');
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const fetchFullApprovalDetails = async (approvalId: string): Promise<ApprovalRequest> => {
    const detailed = await api.getApproval(approvalId);
    try {
      if (detailed.ticket_id) {
        detailed.ticket = await api.getTicket(detailed.ticket_id);
      }
    } catch (e) {
      console.warn('Could not load ticket for approval', e);
    }
    try {
      if (detailed.run_id) {
        detailed.run = await api.getRun(detailed.run_id);
        const props = await api.getRunProposal(detailed.run_id);
        detailed.action = props.find((p) => p.id === detailed.action_id) || props[0];
        const evs = await api.getRunEvidence(detailed.run_id);
        setEvidence(evs);
      }
    } catch (e) {
      console.warn('Could not load action, run or evidence for approval', e);
    }
    return detailed;
  };

  const fetchApprovals = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listApprovals({
        status: statusFilter || undefined,
      });
      setApprovals(list);

      // If we had a selected approval, refresh its detail
      if (selectedApproval) {
        const found = list.find((a) => a.id === selectedApproval.id);
        if (found) {
          const detailed = await fetchFullApprovalDetails(found.id);
          setSelectedApproval(detailed);
        } else if (list.length > 0) {
          const first = await fetchFullApprovalDetails(list[0].id);
          setSelectedApproval(first);
        } else {
          setSelectedApproval(null);
          setEvidence([]);
        }
      } else if (list.length > 0) {
        const first = await fetchFullApprovalDetails(list[0].id);
        setSelectedApproval(first);
      } else {
        setSelectedApproval(null);
        setEvidence([]);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch approval requests');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, [statusFilter]);

  const handleSelectApproval = async (item: ApprovalRequest) => {
    try {
      const detailed = await fetchFullApprovalDetails(item.id);
      setSelectedApproval(detailed);
      setDecisionNote('');
      setActionSuccessMessage(null);
    } catch (err: any) {
      alert(`Could not load approval details: ${err.message}`);
    }
  };

  const handleDecision = async (decision: 'approve' | 'reject') => {
    if (!selectedApproval) return;
    if (currentUser?.role !== 'admin') {
      alert('Forbidden: Only users with the "admin" role can authorize or reject approval requests.');
      return;
    }

    setSubmittingAction(true);
    setActionSuccessMessage(null);
    try {
      let updated: ApprovalRequest;
      if (decision === 'approve') {
        updated = await api.approveAction(selectedApproval.id, decisionNote);
        setActionSuccessMessage(
          'Action successfully approved. The worker is now executing the action and completing the run.'
        );
      } else {
        updated = await api.rejectAction(selectedApproval.id, decisionNote);
        setActionSuccessMessage('Action rejected. The run proposal has been declined.');
      }
      setSelectedApproval(updated);
      setDecisionNote('');
      // Refresh list
      const list = await api.listApprovals({ status: statusFilter || undefined });
      setApprovals(list);
    } catch (err: any) {
      if (err instanceof ApiError) {
        alert(`Action failed: ${err.message} (${err.code})`);
      } else {
        alert(`Action failed: ${err.message}`);
      }
    } finally {
      setSubmittingAction(false);
    }
  };

  const isAdmin = currentUser?.role === 'admin';

  return (
    <div className="rf-page-container">
      {/* Page Title & Stats */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1
              style={{
                fontSize: '24px',
                fontWeight: 700,
                letterSpacing: '-0.02em',
                color: '#f8fafc',
              }}
            >
              Human-in-the-Loop Approval Queue
            </h1>
            <span
              style={{
                padding: '3px 10px',
                borderRadius: '999px',
                fontSize: '12px',
                fontWeight: 700,
                backgroundColor: 'rgba(251, 191, 36, 0.15)',
                color: '#fbbf24',
                border: '1px solid rgba(251, 191, 36, 0.3)',
              }}
            >
              {approvals.filter((a) => a.status === 'pending').length} Pending
            </span>
          </div>
          <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '4px' }}>
            Deterministic risk guardrails pause sensitive actions (refunds, credential resets, external tools)
            until explicitly authorized by an admin.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <select
            className="rf-select"
            style={{ width: 'auto', minWidth: '150px' }}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending Only</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          <button
            onClick={fetchApprovals}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh Approvals"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {!isAdmin && (
        <div
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '20px',
            fontSize: '13px',
            color: '#38bdf8',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <Info size={16} style={{ flexShrink: 0 }} />
          <span>
            You are logged in with the <strong>{currentUser?.role || 'Guest'}</strong> role. You can view
            approval telemetry and supporting evidence, but executing decisions requires the <strong>admin</strong> role.
          </span>
        </div>
      )}

      {actionSuccessMessage && (
        <div
          style={{
            backgroundColor: 'rgba(52, 211, 153, 0.12)',
            border: '1px solid rgba(52, 211, 153, 0.3)',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '20px',
            fontSize: '13px',
            color: '#34d399',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{actionSuccessMessage}</span>
          <button
            onClick={() => setActionSuccessMessage(null)}
            className="rf-btn rf-btn-ghost rf-btn-sm"
            style={{ color: '#34d399' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Split Layout: Left List / Right Inspector */}
      {loading && approvals.length === 0 ? (
        <LoadingSpinner message="Loading pending approval items..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={fetchApprovals} />
      ) : approvals.length === 0 ? (
        <div
          className="rf-card"
          style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}
        >
          <ShieldCheck size={44} style={{ opacity: 0.5, marginBottom: '12px', color: '#34d399' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#f8fafc', marginBottom: '6px' }}>
            No approvals in queue
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
            All agent proposals have either passed policy checks autonomously, or have already been reviewed.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(320px, 1fr) minmax(480px, 1.8fr)',
            gap: '20px',
            alignItems: 'start',
          }}
        >
          {/* Left Column: Queue Items */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: '#64748b',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                padding: '0 4px',
              }}
            >
              Approval Requests ({approvals.length})
            </div>

            {approvals.map((item) => {
              const isSelected = selectedApproval?.id === item.id;
              const isPending = item.status === 'pending';

              return (
                <div
                  key={item.id}
                  onClick={() => handleSelectApproval(item)}
                  className="rf-card"
                  style={{
                    padding: '16px 18px',
                    cursor: 'pointer',
                    borderColor: isSelected
                      ? 'var(--primary-500)'
                      : isPending
                      ? 'rgba(251, 191, 36, 0.3)'
                      : 'var(--border-subtle)',
                    backgroundColor: isSelected
                      ? 'var(--color-surface-hover)'
                      : 'var(--color-surface-base)',
                    boxShadow: isSelected ? '0 0 12px var(--primary-glow)' : undefined,
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '11px',
                        color: '#94a3b8',
                      }}
                    >
                      ID: {item.id.slice(0, 8)}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <StatusBadge status={item.status} size="sm" />
                      {item.status === 'pending' && item.is_actionable === false && (
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            backgroundColor: 'rgba(239, 68, 68, 0.15)',
                            color: '#f87171',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                          }}
                        >
                          Inactive
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ fontWeight: 600, fontSize: '13px', color: '#f8fafc', marginBottom: '6px' }}>
                    Reason: {item.reason}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '11px',
                      color: '#64748b',
                    }}
                  >
                    <span style={{ fontFamily: 'var(--font-mono)' }}>
                      Run: {item.run_id ? item.run_id.slice(0, 8) : 'N/A'}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={11} />
                      <span>{new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Detailed Inspector */}
          {selectedApproval ? (
            <div className="rf-card" style={{ padding: '24px 28px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  marginBottom: '20px',
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      color: 'var(--primary-400)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                      marginBottom: '4px',
                    }}
                  >
                    Approval Request Details
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>
                    Action ID: {selectedApproval.action_id?.slice(0, 8) || selectedApproval.id.slice(0, 8)}
                  </h2>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {selectedApproval.status === 'pending' && (
                    selectedApproval.is_actionable === false ||
                    (selectedApproval.run && selectedApproval.run.status !== 'awaiting_approval') ||
                    (selectedApproval.run_status && selectedApproval.run_status !== 'awaiting_approval') ||
                    (selectedApproval.ticket_status && selectedApproval.ticket_status !== 'pending_approval')
                  ) && (
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        color: '#f87171',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                      }}
                    >
                      Inactive / Conflict
                    </span>
                  )}
                  <StatusBadge status={selectedApproval.status} size="md" />
                </div>
              </div>

              {/* Policy Reason Box */}
              <div
                style={{
                  backgroundColor: 'rgba(251, 191, 36, 0.08)',
                  border: '1px solid rgba(251, 191, 36, 0.3)',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  marginBottom: '20px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: '#fbbf24',
                    fontWeight: 600,
                    fontSize: '13px',
                    marginBottom: '4px',
                  }}
                >
                  <AlertTriangle size={15} />
                  <span>Deterministic Risk Engine Intercept</span>
                </div>
                <div style={{ fontSize: '13px', color: '#fde68a' }}>
                  {selectedApproval.reason}
                </div>
              </div>

              {/* Associated Ticket Info */}
              {selectedApproval.ticket && (
                <div
                  style={{
                    backgroundColor: 'var(--color-surface-raised)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '14px 18px',
                    marginBottom: '20px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px',
                    }}
                  >
                    <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>
                      Originating Support Ticket
                    </span>
                    <button
                      onClick={() => onSelectTicket(selectedApproval.ticket!.id)}
                      className="rf-btn rf-btn-ghost rf-btn-sm"
                      style={{ color: 'var(--primary-400)', padding: '2px 6px' }}
                    >
                      <span>Open Ticket</span>
                      <ExternalLink size={12} />
                    </button>
                  </div>
                  <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '14px', marginBottom: '4px' }}>
                    {selectedApproval.ticket.subject}
                  </div>
                  <div style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: 1.4 }}>
                    {selectedApproval.ticket.body}
                  </div>
                </div>
              )}

              {/* Action Payload & Draft Response */}
              {selectedApproval.action && (
                <div style={{ marginBottom: '20px' }}>
                  <div
                    style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#94a3b8',
                      marginBottom: '8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    Proposed Action Payload
                  </div>
                  <div
                    style={{
                      backgroundColor: 'var(--color-canvas)',
                      border: '1px solid var(--border-default)',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '12px',
                      color: '#e2e8f0',
                      overflowX: 'auto',
                      marginBottom: '14px',
                    }}
                  >
                    <div style={{ color: 'var(--primary-400)', marginBottom: '4px' }}>
                      Action Type: {selectedApproval.action.action_type}
                    </div>
                    <pre style={{ margin: 0 }}>
                      {JSON.stringify(selectedApproval.action.params, null, 2)}
                    </pre>
                  </div>

                  {selectedApproval.action.draft_response && (
                    <div>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: '#94a3b8',
                          marginBottom: '6px',
                        }}
                      >
                        Model Proposed Customer Response
                      </div>
                      <div
                        style={{
                          backgroundColor: 'var(--color-surface-raised)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                          padding: '12px 16px',
                          fontSize: '13px',
                          color: '#cbd5e1',
                          lineHeight: 1.5,
                        }}
                      >
                        {selectedApproval.action.draft_response}
                      </div>
                    </div>
                  )}

                  {/* Grounded Evidence Citations */}
                  {evidence.length > 0 && (
                    <div style={{ marginTop: '16px' }}>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 600,
                          color: '#94a3b8',
                          marginBottom: '8px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                        }}
                      >
                        Supporting Knowledge Evidence ({evidence.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {evidence.map((ev) => (
                          <div
                            key={ev.id}
                            style={{
                              backgroundColor: 'var(--color-surface-raised)',
                              border: '1px solid var(--border-subtle)',
                              borderRadius: '6px',
                              padding: '10px 14px',
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: '4px',
                              }}
                            >
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#f8fafc' }}>
                                {ev.document_title}
                              </span>
                              <span style={{ fontSize: '11px', color: '#34d399', fontWeight: 600 }}>
                                Score: {typeof ev.score === 'number' ? ev.score.toFixed(3) : '1.000'}
                              </span>
                            </div>
                            <div
                              style={{
                                fontSize: '12px',
                                color: '#cbd5e1',
                                fontStyle: 'italic',
                                backgroundColor: 'var(--color-canvas)',
                                padding: '6px 10px',
                                borderRadius: '4px',
                                borderLeft: '2px solid var(--primary-500)',
                              }}
                            >
                              "{ev.excerpt}"
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Historical Decision Info (if already resolved) */}
              {selectedApproval.status !== 'pending' && (
                <div
                  style={{
                    backgroundColor: 'var(--color-surface-raised)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '14px 18px',
                    marginBottom: '20px',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
                    Decision Outcome
                  </div>
                  <div style={{ fontSize: '13px', color: '#f8fafc' }}>
                    Status: <strong style={{ textTransform: 'capitalize' }}>{selectedApproval.status}</strong>
                  </div>
                  {selectedApproval.decision_note && (
                    <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '4px' }}>
                      Reviewer Note: "{selectedApproval.decision_note}"
                    </div>
                  )}
                  {selectedApproval.decided_at && (
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px' }}>
                      Decided at: {new Date(selectedApproval.decided_at).toLocaleString()}
                    </div>
                  )}
                </div>
              )}

              {/* Action Decision Form (only if pending) */}
              {selectedApproval.status === 'pending' && (
                (selectedApproval.is_actionable === false ||
                  (selectedApproval.run && selectedApproval.run.status !== 'awaiting_approval') ||
                  (selectedApproval.run_status && selectedApproval.run_status !== 'awaiting_approval') ||
                  (selectedApproval.ticket_status && selectedApproval.ticket_status !== 'pending_approval')) ? (
                  <div
                    style={{
                      borderTop: '1px solid var(--border-subtle)',
                      paddingTop: '20px',
                      marginTop: '20px',
                    }}
                  >
                    <div
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.08)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '8px',
                        padding: '16px 20px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          color: '#f87171',
                          fontWeight: 600,
                          fontSize: '14px',
                          marginBottom: '8px',
                        }}
                      >
                        <AlertTriangle size={18} />
                        <span>Approval Request Inactive (State Conflict)</span>
                      </div>
                      <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.5, marginBottom: '12px' }}>
                        This approval request cannot be executed because its underlying agent run or ticket state is no longer awaiting approval.
                        {selectedApproval.stale_reason ? ` (${selectedApproval.stale_reason})` : ''}
                      </p>
                      <div
                        style={{
                          fontSize: '12px',
                          color: '#94a3b8',
                          backgroundColor: 'var(--color-canvas)',
                          padding: '10px 14px',
                          borderRadius: '6px',
                          marginBottom: '14px',
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                          gap: '8px',
                        }}
                      >
                        <div>
                          <strong>Agent Run Status:</strong>{' '}
                          <span style={{ color: '#f8fafc', textTransform: 'capitalize' }}>
                            {selectedApproval.run?.status || selectedApproval.run_status || 'unknown'}
                          </span>
                        </div>
                        <div>
                          <strong>Ticket Status:</strong>{' '}
                          <span style={{ color: '#f8fafc', textTransform: 'capitalize' }}>
                            {selectedApproval.ticket?.status || selectedApproval.ticket_status || 'unknown'}
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                        <span style={{ fontSize: '12px', color: '#64748b' }}>
                          Audit history preserved for compliance. No execution permitted.
                        </span>
                        <button
                          onClick={() => onSelectTicket(selectedApproval.ticket_id)}
                          className="rf-btn rf-btn-secondary"
                          style={{ padding: '6px 14px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                        >
                          <ExternalLink size={13} />
                          <span>Inspect Ticket Telemetry & History</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      borderTop: '1px solid var(--border-subtle)',
                      paddingTop: '20px',
                      marginTop: '20px',
                    }}
                  >
                    <label
                      style={{
                        display: 'block',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: '#cbd5e1',
                        marginBottom: '6px',
                      }}
                    >
                      Supervisor Decision Note (Optional)
                    </label>
                    <textarea
                      className="rf-textarea"
                      rows={2}
                      placeholder="Provide justification or context for this approval/rejection..."
                      value={decisionNote}
                      onChange={(e) => setDecisionNote(e.target.value)}
                      style={{ marginBottom: '16px' }}
                      disabled={!isAdmin || submittingAction}
                    />

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>
                      <button
                        onClick={() => handleDecision('reject')}
                        className="rf-btn rf-btn-danger"
                        disabled={!isAdmin || submittingAction}
                        style={{ padding: '8px 18px' }}
                      >
                        <XCircle size={15} />
                        <span>{submittingAction ? 'Processing...' : 'Reject Action'}</span>
                      </button>
                      <button
                        onClick={() => handleDecision('approve')}
                        className="rf-btn rf-btn-primary"
                        disabled={!isAdmin || submittingAction}
                        style={{
                          padding: '8px 22px',
                          backgroundColor: '#10b981',
                          borderColor: '#059669',
                        }}
                      >
                        <CheckCircle size={15} />
                        <span>{submittingAction ? 'Processing...' : 'Approve & Execute Action'}</span>
                      </button>
                    </div>
                  </div>
                )
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};
