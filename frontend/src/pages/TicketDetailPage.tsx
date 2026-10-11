import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  BookOpen,
  Clock,
  Cpu,
  Edit2,
  History,
  Play,
  RefreshCw,
  Save,
  Shield,
  X,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import { PriorityBadge, StatusBadge } from '../components/StatusBadge';
import type {
  AgentRun,
  EvidenceItem,
  ProposalAction,
  StatusHistoryItem,
  Ticket,
  TicketEvent,
  TicketPriority,
} from '../types';

interface TicketDetailPageProps {
  ticketId: string;
  onBack: () => void;
  onNavigateToApprovals: () => void;
}

export const TicketDetailPage: React.FC<TicketDetailPageProps> = ({
  ticketId,
  onBack,
  onNavigateToApprovals,
}) => {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [proposal, setProposal] = useState<ProposalAction[]>([]);
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [statusHistory, setStatusHistory] = useState<StatusHistoryItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Triggering run & polling state
  const [triggeringRun, setTriggeringRun] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  // Edit ticket state
  const [isEditing, setIsEditing] = useState(false);
  const [editSubject, setEditSubject] = useState('');
  const [editBody, setEditBody] = useState('');
  const [editPriority, setEditPriority] = useState<TicketPriority>('medium');
  const [savingEdit, setSavingEdit] = useState(false);

  const fetchTicketData = async () => {
    try {
      const [tData, runsData, eventsData, historyData] = await Promise.all([
        api.getTicket(ticketId),
        api.getTicketRuns(ticketId),
        api.getTicketEvents(ticketId),
        api.getTicketStatusHistory(ticketId),
      ]);

      setTicket(tData);
      setRuns(runsData);
      setEvents(eventsData);
      setStatusHistory(historyData);

      // Initialize edit fields
      setEditSubject(tData.subject);
      setEditBody(tData.body);
      setEditPriority(tData.priority);

      // Select active or latest run
      if (runsData.length > 0) {
        const activeRun = runsData.find((r) => r.status === 'queued' || r.status === 'running') || runsData[0];
        setSelectedRun(activeRun);
        loadRunDetails(activeRun.id);

        // If run is in flight, enable polling
        if (activeRun.status === 'queued' || activeRun.status === 'running') {
          setIsPolling(true);
        } else {
          setIsPolling(false);
        }
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch ticket data');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetails = async (runId: string) => {
    try {
      const [evidenceData, proposalData] = await Promise.all([
        api.getRunEvidence(runId),
        api.getRunProposal(runId),
      ]);
      setEvidence(evidenceData);
      setProposal(proposalData);
    } catch (err) {
      console.warn('Could not load run details', err);
    }
  };

  useEffect(() => {
    fetchTicketData();
  }, [ticketId]);

  // Polling effect when run is in flight
  useEffect(() => {
    if (!isPolling) return;
    const interval = setInterval(async () => {
      try {
        const [tData, runsData, eventsData] = await Promise.all([
          api.getTicket(ticketId),
          api.getTicketRuns(ticketId),
          api.getTicketEvents(ticketId),
        ]);
        setTicket(tData);
        setRuns(runsData);
        setEvents(eventsData);

        const active = runsData.find((r) => r.status === 'queued' || r.status === 'running');
        if (!active) {
          setIsPolling(false);
          if (runsData.length > 0) {
            setSelectedRun(runsData[0]);
            loadRunDetails(runsData[0].id);
          }
        } else {
          setSelectedRun(active);
          loadRunDetails(active.id);
        }
      } catch (err) {
        console.error('Polling error', err);
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [isPolling, ticketId]);

  const handleSelectRun = (run: AgentRun) => {
    setSelectedRun(run);
    loadRunDetails(run.id);
  };

  const handleTriggerRun = async () => {
    setTriggeringRun(true);
    try {
      const newRun = await api.triggerRun(ticketId);
      setSelectedRun(newRun);
      setIsPolling(true);
      await fetchTicketData();
    } catch (err: any) {
      alert(`Could not trigger agent run: ${err.message}`);
    } finally {
      setTriggeringRun(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!ticket) return;
    setSavingEdit(true);
    try {
      const updated = await api.updateTicket(ticket.id, {
        subject: editSubject,
        body: editBody,
        priority: editPriority,
      });
      setTicket(updated);
      setIsEditing(false);
    } catch (err: any) {
      alert(`Failed to update ticket: ${err.message}`);
    } finally {
      setSavingEdit(false);
    }
  };

  if (loading && !ticket) {
    return <LoadingSpinner message="Loading ticket execution telemetry..." size="lg" />;
  }

  if (error && !ticket) {
    return (
      <div className="rf-page-container">
        <ErrorAlert message={error} onRetry={fetchTicketData} />
      </div>
    );
  }

  if (!ticket) return null;

  return (
    <div className="rf-page-container">
      {/* Top Header Navigation */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '20px',
        }}
      >
        <button
          onClick={onBack}
          className="rf-btn rf-btn-ghost rf-btn-sm"
          style={{ color: '#94a3b8', gap: '6px' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Ticket Queue</span>
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isPolling && (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '12px',
                color: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                padding: '4px 10px',
                borderRadius: '999px',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}
            >
              <RefreshCw size={12} className="spin" />
              <span>Agent run in flight...</span>
            </div>
          )}

          <button
            onClick={fetchTicketData}
            className="rf-btn rf-btn-secondary rf-btn-sm"
            title="Refresh ticket"
          >
            <RefreshCw size={13} />
            <span>Refresh</span>
          </button>

          {ticket.status !== 'processing' && (
            <button
              onClick={handleTriggerRun}
              className="rf-btn rf-btn-primary rf-btn-sm"
              disabled={triggeringRun || isPolling}
            >
              <Play size={13} />
              <span>{triggeringRun ? 'Starting...' : 'Trigger Run'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Ticket Banner Card */}
      <div className="rf-card" style={{ marginBottom: '24px', padding: '24px 28px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
            marginBottom: '16px',
          }}
        >
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                marginBottom: '8px',
                flexWrap: 'wrap',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  color: 'var(--primary-400)',
                  backgroundColor: 'rgba(99, 102, 241, 0.12)',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                }}
              >
                {ticket.id}
              </span>
              <StatusBadge status={ticket.status} size="md" />
              <PriorityBadge priority={ticket.priority} />
              {ticket.category && (
                <span
                  style={{
                    fontSize: '12px',
                    color: '#cbd5e1',
                    textTransform: 'capitalize',
                    backgroundColor: 'var(--color-surface-raised)',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  {ticket.category}
                </span>
              )}
            </div>

            {isEditing ? (
              <div style={{ marginTop: '10px' }}>
                <input
                  type="text"
                  className="rf-input"
                  value={editSubject}
                  onChange={(e) => setEditSubject(e.target.value)}
                  style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}
                />
              </div>
            ) : (
              <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                {ticket.subject}
              </h1>
            )}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {isEditing ? (
              <>
                <button
                  onClick={() => setIsEditing(false)}
                  className="rf-btn rf-btn-secondary rf-btn-sm"
                  disabled={savingEdit}
                >
                  <X size={13} />
                  <span>Cancel</span>
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="rf-btn rf-btn-primary rf-btn-sm"
                  disabled={savingEdit}
                >
                  <Save size={13} />
                  <span>{savingEdit ? 'Saving...' : 'Save Changes'}</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => setIsEditing(true)}
                className="rf-btn rf-btn-secondary rf-btn-sm"
                title="Edit ticket subject or priority"
              >
                <Edit2 size={13} />
                <span>Edit</span>
              </button>
            )}
          </div>
        </div>

        {/* Metadata Strip */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '24px',
            fontSize: '12px',
            color: '#94a3b8',
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: '16px',
          }}
        >
          <div>
            <strong style={{ color: '#cbd5e1' }}>Requester: </strong>
            <span>{ticket.requester_email || 'Not specified'}</span>
          </div>
          <div>
            <strong style={{ color: '#cbd5e1' }}>Created: </strong>
            <span>{new Date(ticket.created_at).toLocaleString()}</span>
          </div>
          {ticket.resolved_at && (
            <div>
              <strong style={{ color: '#34d399' }}>Resolved: </strong>
              <span>{new Date(ticket.resolved_at).toLocaleString()}</span>
            </div>
          )}
          {ticket.assigned_queue && (
            <div>
              <strong style={{ color: '#cbd5e1' }}>Queue: </strong>
              <span>{ticket.assigned_queue}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Split Grid: Context on Left, AI Execution on Right */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(340px, 1fr) minmax(460px, 1.4fr)',
          gap: '24px',
          alignItems: 'start',
        }}
      >
        {/* Left Column: Ticket Body, Status History & Audit Log */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Customer Ticket Body Card */}
          <div className="rf-card">
            <h2 style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc', marginBottom: '12px' }}>
              Customer Message
            </h2>
            {isEditing ? (
              <div>
                <textarea
                  className="rf-textarea"
                  rows={4}
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  style={{ marginBottom: '10px' }}
                />
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <label style={{ fontSize: '12px', color: '#cbd5e1' }}>Priority:</label>
                  <select
                    className="rf-select"
                    style={{ width: 'auto' }}
                    value={editPriority}
                    onChange={(e) => setEditPriority(e.target.value as any)}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>
            ) : (
              <div
                style={{
                  backgroundColor: 'var(--color-surface-raised)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '14px 16px',
                  fontSize: '13px',
                  color: '#e2e8f0',
                  lineHeight: 1.6,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {ticket.body}
              </div>
            )}
          </div>

          {/* Ticket Status History Timeline */}
          <div className="rf-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Clock size={16} color="var(--primary-400)" />
              <h2 style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                Status Transitions
              </h2>
            </div>

            {statusHistory.length === 0 ? (
              <div style={{ fontSize: '12px', color: '#64748b' }}>No status transitions recorded.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {statusHistory.map((sh, idx) => (
                  <div
                    key={`sh-${idx}-${sh.created_at || idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      fontSize: '12px',
                    }}
                  >
                    <div
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: 'var(--primary-400)',
                        marginTop: '5px',
                        flexShrink: 0,
                      }}
                    />
                    <div>
                      <div style={{ color: '#cbd5e1' }}>
                        Transitioned to <strong style={{ color: '#f8fafc' }}>{sh.to_status}</strong>
                        {sh.from_status ? ` from ${sh.from_status}` : ''}
                      </div>
                      {sh.reason && (
                        <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '2px' }}>
                          Reason: {sh.reason}
                        </div>
                      )}
                      <div style={{ color: '#64748b', fontSize: '11px', marginTop: '2px' }}>
                        {new Date(sh.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Immutable Audit Events Stream */}
          <div className="rf-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <History size={16} color="#38bdf8" />
              <h2 style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                Immutable Audit Events ({events.length})
              </h2>
            </div>

            {events.length === 0 ? (
              <div style={{ fontSize: '12px', color: '#64748b' }}>No audit events emitted yet.</div>
            ) : (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  maxHeight: '400px',
                  overflowY: 'auto',
                }}
              >
                {events.map((ev) => (
                  <div
                    key={ev.id}
                    style={{
                      backgroundColor: 'var(--color-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '6px',
                      padding: '10px 12px',
                      fontSize: '12px',
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
                      <strong style={{ color: '#f1f5f9' }}>{ev.event_type}</strong>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>
                        {new Date(ev.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                      Actor: <span style={{ color: '#cbd5e1' }}>{ev.actor_type}</span>
                      {ev.run_id && ` • Run: ${ev.run_id.slice(0, 8)}`}
                    </div>
                    {ev.detail && Object.keys(ev.detail).length > 0 && (
                      <pre
                        style={{
                          backgroundColor: 'var(--color-canvas)',
                          padding: '6px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontFamily: 'var(--font-mono)',
                          color: '#94a3b8',
                          margin: 0,
                          overflowX: 'auto',
                        }}
                      >
                        {JSON.stringify(ev.detail, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: AI Agent Execution Inspector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Runs Selector Tab Strip */}
          <div className="rf-card" style={{ padding: '16px 20px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={16} color="var(--primary-400)" />
                <h2 style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                  Agent Runs ({runs.length})
                </h2>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b' }}>
                Select a run to view proposal & citations
              </span>
            </div>

            {runs.length === 0 ? (
              <div
                style={{
                  padding: '24px',
                  textAlign: 'center',
                  backgroundColor: 'var(--color-surface-raised)',
                  borderRadius: '8px',
                  color: '#64748b',
                }}
              >
                <p style={{ fontSize: '13px', marginBottom: '12px' }}>
                  No agent runs executed for this ticket yet.
                </p>
                <button onClick={handleTriggerRun} className="rf-btn rf-btn-primary rf-btn-sm">
                  <Play size={13} />
                  <span>Start Autonomous Run</span>
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
                {runs.map((r, i) => {
                  const isSel = selectedRun?.id === r.id;
                  return (
                    <button
                      key={r.id}
                      onClick={() => handleSelectRun(r)}
                      style={{
                        padding: '8px 14px',
                        borderRadius: '6px',
                        backgroundColor: isSel
                          ? 'var(--color-surface-hover)'
                          : 'var(--color-surface-raised)',
                        border: isSel ? '1px solid var(--primary-500)' : '1px solid var(--border-subtle)',
                        color: isSel ? '#ffffff' : '#94a3b8',
                        cursor: 'pointer',
                        textAlign: 'left',
                        flexShrink: 0,
                      }}
                    >
                      <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        Run #{runs.length - i} ({r.id.slice(0, 6)})
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px' }}>
                        <StatusBadge status={r.status} size="sm" />
                        {r.duration_ms && (
                          <span style={{ fontSize: '10px', color: '#64748b' }}>{r.duration_ms}ms</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selected Run Telemetry & Execution Outcome */}
          {selectedRun && (
            <>
              {/* Policy Decision & Proposal Actions */}
              <div className="rf-card">
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Shield size={16} color="var(--primary-400)" />
                    <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#f8fafc' }}>
                      Policy Decision & Proposed Action
                    </h2>
                  </div>
                  {selectedRun.disposition && (
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor:
                          selectedRun.disposition === 'resolved'
                            ? 'rgba(52, 211, 153, 0.15)'
                            : 'rgba(251, 191, 36, 0.15)',
                        color: selectedRun.disposition === 'resolved' ? '#34d399' : '#fbbf24',
                      }}
                    >
                      Disposition: {selectedRun.disposition}
                    </span>
                  )}
                </div>

                {proposal.length === 0 ? (
                  <div
                    style={{
                      padding: '20px',
                      textAlign: 'center',
                      backgroundColor: 'var(--color-surface-raised)',
                      borderRadius: '8px',
                      color: '#94a3b8',
                      fontSize: '13px',
                    }}
                  >
                    {selectedRun.status === 'queued' || selectedRun.status === 'running'
                      ? 'The agent workflow is currently classifying, retrieving knowledge, and proposing actions...'
                      : 'No actions were proposed for this run.'}
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {proposal.map((action) => {
                      const isAllowed = action.policy_decision === 'allow';
                      const isRequireApproval = action.policy_decision === 'require_approval';

                      return (
                        <div
                          key={action.id}
                          style={{
                            border: '1px solid var(--border-default)',
                            borderRadius: '8px',
                            backgroundColor: 'var(--color-surface-raised)',
                            padding: '16px 18px',
                          }}
                        >
                          {/* Policy Decision Banner */}
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginBottom: '12px',
                              paddingBottom: '10px',
                              borderBottom: '1px solid var(--border-subtle)',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span
                                style={{
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  color: isAllowed
                                    ? '#34d399'
                                    : isRequireApproval
                                    ? '#fbbf24'
                                    : '#f87171',
                                }}
                              >
                                Policy: {action.policy_decision}
                              </span>
                              <span style={{ fontSize: '12px', color: '#64748b' }}>•</span>
                              <span style={{ fontSize: '12px', color: '#cbd5e1' }}>
                                Action: <strong>{action.action_type}</strong>
                              </span>
                            </div>
                            <StatusBadge status={action.status} size="sm" />
                          </div>

                          {/* Policy Reasons */}
                          {action.policy_reasons && action.policy_reasons.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <div
                                style={{
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  color: '#94a3b8',
                                  textTransform: 'uppercase',
                                  marginBottom: '4px',
                                }}
                              >
                                Application Policy Reasoning
                              </div>
                              <ul
                                style={{
                                  margin: 0,
                                  paddingLeft: '16px',
                                  fontSize: '12px',
                                  color: '#e2e8f0',
                                }}
                              >
                                {action.policy_reasons.map((r, idx) => (
                                  <li key={idx}>{r}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {isRequireApproval && action.status === 'pending_approval' && (
                            <div
                              style={{
                                backgroundColor: 'rgba(251, 191, 36, 0.1)',
                                border: '1px solid rgba(251, 191, 36, 0.3)',
                                borderRadius: '6px',
                                padding: '10px 12px',
                                marginBottom: '12px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                              }}
                            >
                              <div style={{ fontSize: '12px', color: '#fbbf24' }}>
                                This action is currently pending human sign-off in the Approval Queue.
                              </div>
                              <button
                                onClick={onNavigateToApprovals}
                                className="rf-btn rf-btn-primary rf-btn-sm"
                                style={{
                                  backgroundColor: '#fbbf24',
                                  color: '#000',
                                  fontWeight: 600,
                                  fontSize: '11px',
                                }}
                              >
                                Review Approval
                              </button>
                            </div>
                          )}

                          {/* Draft Response */}
                          {action.draft_response && (
                            <div style={{ marginBottom: '12px' }}>
                              <div
                                style={{
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  color: '#94a3b8',
                                  textTransform: 'uppercase',
                                  marginBottom: '4px',
                                }}
                              >
                                Model Proposed Response
                              </div>
                              <div
                                style={{
                                  backgroundColor: 'var(--color-canvas)',
                                  border: '1px solid var(--border-subtle)',
                                  borderRadius: '6px',
                                  padding: '12px 14px',
                                  fontSize: '13px',
                                  color: '#f1f5f9',
                                  lineHeight: 1.5,
                                }}
                              >
                                {action.draft_response}
                              </div>
                            </div>
                          )}

                          {/* Action Parameters */}
                          <div>
                            <div
                              style={{
                                fontSize: '11px',
                                fontWeight: 600,
                                color: '#94a3b8',
                                textTransform: 'uppercase',
                                marginBottom: '4px',
                              }}
                            >
                              Parameters & Result
                            </div>
                            <pre
                              style={{
                                backgroundColor: 'var(--color-canvas)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: '6px',
                                padding: '8px 12px',
                                fontSize: '11px',
                                fontFamily: 'var(--font-mono)',
                                color: '#94a3b8',
                                margin: 0,
                                overflowX: 'auto',
                              }}
                            >
                              {JSON.stringify({ params: action.params, result: action.result }, null, 2)}
                            </pre>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Grounded Knowledge Evidence Viewer */}
              <div className="rf-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <BookOpen size={16} color="#34d399" />
                  <h2 style={{ fontSize: '15px', fontWeight: 600, color: '#f8fafc' }}>
                    Grounded Knowledge Citations ({evidence.length})
                  </h2>
                </div>

                {evidence.length === 0 ? (
                  <div
                    style={{
                      padding: '20px',
                      textAlign: 'center',
                      backgroundColor: 'var(--color-surface-raised)',
                      borderRadius: '8px',
                      color: '#64748b',
                      fontSize: '13px',
                    }}
                  >
                    No knowledge citations were retrieved for this run.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {evidence.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          backgroundColor: 'var(--color-surface-raised)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                          padding: '14px 16px',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: '6px',
                          }}
                        >
                          <div style={{ fontWeight: 600, fontSize: '13px', color: '#f8fafc' }}>
                            {item.document_title}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {proposal.some((a) => a.cited_evidence_ids?.includes(item.chunk_id)) && (
                              <span
                                style={{
                                  fontSize: '11px',
                                  padding: '1px 8px',
                                  borderRadius: '4px',
                                  backgroundColor: 'rgba(52, 211, 153, 0.15)',
                                  color: '#34d399',
                                  border: '1px solid rgba(52, 211, 153, 0.3)',
                                  fontWeight: 600,
                                }}
                              >
                                Cited in Draft
                              </span>
                            )}
                            <span
                              style={{
                                fontSize: '11px',
                                textTransform: 'uppercase',
                                padding: '1px 6px',
                                borderRadius: '4px',
                                backgroundColor:
                                  item.retrieval_mode === 'vector'
                                    ? 'rgba(99, 102, 241, 0.15)'
                                    : 'rgba(56, 189, 248, 0.15)',
                                color:
                                  item.retrieval_mode === 'vector'
                                    ? 'var(--primary-400)'
                                    : '#38bdf8',
                                fontWeight: 600,
                              }}
                            >
                              {item.retrieval_mode}
                            </span>
                            <span style={{ fontSize: '11px', color: '#34d399', fontWeight: 600 }}>
                              Score: {item.score.toFixed(3)}
                            </span>
                          </div>
                        </div>
                        <div
                          style={{
                            backgroundColor: 'var(--color-canvas)',
                            borderLeft: '3px solid var(--primary-500)',
                            padding: '8px 12px',
                            borderRadius: '0 4px 4px 0',
                            fontSize: '12px',
                            color: '#cbd5e1',
                            lineHeight: 1.5,
                            fontStyle: 'italic',
                          }}
                        >
                          "{item.excerpt}"
                        </div>
                        <div
                          style={{
                            fontSize: '10px',
                            color: '#64748b',
                            fontFamily: 'var(--font-mono)',
                            marginTop: '6px',
                          }}
                        >
                          Chunk ID: {item.chunk_id.slice(0, 8)} • Document ID: {item.document_id.slice(0, 8)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
