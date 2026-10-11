import React, { useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle,
  Info,
  Play,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import type { User } from '../types';

interface EvalsPageProps {
  currentUser: User | null;
}

export const EvalsPage: React.FC<EvalsPageProps> = ({ currentUser }) => {
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedRun, setSelectedRun] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const fetchEvals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listEvalRuns();
      setRuns(data);
      if (selectedRun) {
        const found = data.find((r: any) => r.id === selectedRun.id);
        if (found) {
          loadRunDetail(found.id);
        } else if (data.length > 0) {
          loadRunDetail(data[0].id);
        } else {
          setSelectedRun(null);
        }
      } else if (data.length > 0) {
        loadRunDetail(data[0].id);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch evaluation runs');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetail = async (runId: string) => {
    setLoadingDetails(true);
    try {
      const detailed = await api.getEvalRun(runId);
      setSelectedRun(detailed);
    } catch (err) {
      console.warn('Could not load eval detail', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    fetchEvals();
  }, []);

  const handleTriggerEval = async () => {
    if (currentUser?.role !== 'admin') {
      alert('Forbidden: Triggering evaluations requires the admin role.');
      return;
    }

    setTriggering(true);
    try {
      const newRun = await api.triggerEvalRun('evals/dataset.jsonl');
      await fetchEvals();
      setSelectedRun(newRun);
    } catch (err: any) {
      alert(`Could not start eval run: ${err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const isAdmin = currentUser?.role === 'admin';

  return (
    <div className="rf-page-container">
      {/* Header */}
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
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: '#f8fafc',
              marginBottom: '4px',
            }}
          >
            Model Safety & Policy Evaluations
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Systematic benchmark testing against 32 adversarial test scenarios (injection, citations, sensitive actions).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={fetchEvals}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh Evals"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleTriggerEval}
            className="rf-btn rf-btn-primary"
            disabled={triggering || !isAdmin}
          >
            <Play size={14} />
            <span>{triggering ? 'Running Benchmark...' : 'Run Eval Suite'}</span>
          </button>
        </div>
      </div>

      {/* Honest Limitations Notice */}
      <div
        style={{
          backgroundColor: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: '8px',
          padding: '14px 18px',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
        }}
      >
        <Info size={18} style={{ color: 'var(--primary-400)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.5 }}>
          <strong style={{ color: '#ffffff' }}>Deterministic Provider Verification:</strong> Evaluations
          in this offline test environment run against ResolveFlow's labelled deterministic provider
          using <code style={{ color: 'var(--primary-400)' }}>evals/dataset.jsonl</code>. This verifies
          strict policy gating, approval intercepts, citation verification, and error handling.
          Live OpenAI calls are not simulated or fabricated.
        </div>
      </div>

      {loading && runs.length === 0 ? (
        <LoadingSpinner message="Fetching evaluation suite history..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={fetchEvals} />
      ) : runs.length === 0 ? (
        <div
          className="rf-card"
          style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}
        >
          <Activity size={40} style={{ opacity: 0.4, marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            No evaluation runs on record
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 16px' }}>
            Execute the 32-case deterministic evaluation suite to inspect pass rates and policy decisions.
          </p>
          <button
            onClick={handleTriggerEval}
            className="rf-btn rf-btn-primary"
            disabled={triggering || !isAdmin}
          >
            <Play size={14} />
            <span>Execute Benchmark Suite</span>
          </button>
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
          {/* Left Column: Evaluation Runs List */}
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
              Benchmark Runs ({runs.length})
            </div>

            {runs.map((r) => {
              const isSelected = selectedRun?.id === r.id;
              const totalCases = r.summary?.dataset_size ?? 32;
              const passedCases = r.summary?.passed ?? 0;
              const passPct = r.summary?.pass_rate !== undefined ? r.summary.pass_rate * 100 : (passedCases / (totalCases || 1)) * 100;
              const isPerfect = passPct === 100;

              return (
                <div
                  key={r.id}
                  onClick={() => {
                    setSelectedRun(r);
                    loadRunDetail(r.id);
                  }}
                  className="rf-card"
                  style={{
                    padding: '16px 18px',
                    cursor: 'pointer',
                    borderColor: isSelected ? 'var(--primary-500)' : 'var(--border-subtle)',
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
                      marginBottom: '6px',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        color: 'var(--primary-400)',
                        fontWeight: 600,
                      }}
                    >
                      {r.id.slice(0, 8)}
                    </span>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '999px',
                        backgroundColor: isPerfect
                          ? 'rgba(52, 211, 153, 0.15)'
                          : 'rgba(251, 191, 36, 0.15)',
                        color: isPerfect ? '#34d399' : '#fbbf24',
                      }}
                    >
                      {passPct.toFixed(1)}% Pass
                    </span>
                  </div>

                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc', marginBottom: '8px' }}>
                    {r.dataset_name || 'dataset.jsonl'} • {r.provider || 'deterministic'}
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
                    <span>
                      {passedCases}/{totalCases} cases passed
                    </span>
                    <span>
                      {r.summary?.avg_latency_ms ? `${Math.round(r.summary.avg_latency_ms)}ms avg` : ''} •{' '}
                      {r.started_at ? new Date(r.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Run Details & Cases Breakdown */}
          {selectedRun ? (
            <div className="rf-card" style={{ padding: '24px 28px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  paddingBottom: '16px',
                  borderBottom: '1px solid var(--border-subtle)',
                  marginBottom: '20px',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                    Evaluation Run: {selectedRun.id.slice(0, 8)}
                  </h2>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                    Dataset: {selectedRun.dataset_name} • Provider: {selectedRun.provider || 'deterministic'} •{' '}
                    {selectedRun.started_at ? new Date(selectedRun.started_at).toLocaleString() : ''}
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div
                    style={{
                      fontSize: '22px',
                      fontWeight: 700,
                      color:
                        (selectedRun.summary?.pass_rate ?? 0) === 1 ? '#34d399' : '#fbbf24',
                    }}
                  >
                    {selectedRun.summary?.pass_rate !== undefined
                      ? `${(selectedRun.summary.pass_rate * 100).toFixed(1)}%`
                      : 'N/A'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    {selectedRun.summary?.passed ?? 0} of {selectedRun.summary?.dataset_size ?? 0} Passed
                  </div>
                </div>
              </div>

              {/* Individual Cases Table / List */}
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc', marginBottom: '12px' }}>
                  Scenario Results ({selectedRun.results?.length ?? 0} cases)
                </div>

                {loadingDetails ? (
                  <LoadingSpinner message="Loading scenario cases..." size="sm" />
                ) : !selectedRun.results || selectedRun.results.length === 0 ? (
                  <div
                    style={{
                      padding: '24px',
                      textAlign: 'center',
                      backgroundColor: 'var(--color-surface-raised)',
                      borderRadius: '8px',
                      color: '#94a3b8',
                      fontSize: '13px',
                    }}
                  >
                    All scenarios processed.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '500px', overflowY: 'auto' }}>
                    {selectedRun.results.map((c: any, idx: number) => {
                      const expText =
                        typeof c.expected === 'object' && c.expected !== null
                          ? `${c.expected.category || ''} -> ${c.expected.disposition || c.expected.ticket_status || ''}`
                          : String(c.expected || '');
                      const actText =
                        typeof c.actual === 'object' && c.actual !== null
                          ? `${c.actual.disposition || c.actual.policy_decision || c.actual.ticket_status || ''}`
                          : String(c.actual || 'Pass');

                      return (
                        <div
                          key={idx}
                          style={{
                            backgroundColor: 'var(--color-surface-raised)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '6px',
                            padding: '10px 14px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            fontSize: '12px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            {c.passed !== false ? (
                              <CheckCircle size={15} color="#34d399" />
                            ) : (
                              <XCircle size={15} color="#f87171" />
                            )}
                            <span style={{ fontWeight: 600, color: '#f1f5f9' }}>
                              {c.case_id || `Case #${idx + 1}`}
                            </span>
                          </div>
                          <div style={{ color: '#94a3b8', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {expText && <span>Expected: {expText}</span>}
                            <span>•</span>
                            <span style={{ color: c.passed !== false ? '#34d399' : '#f87171' }}>
                              Actual: {actText}
                            </span>
                            {c.latency_ms && (
                              <span style={{ color: '#64748b' }}>({c.latency_ms}ms)</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};
