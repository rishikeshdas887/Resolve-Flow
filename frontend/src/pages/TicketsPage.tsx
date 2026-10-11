import React, { useEffect, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Play,
  Plus,
  RefreshCw,
  Search,
  Ticket as TicketIcon,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import { PriorityBadge, StatusBadge } from '../components/StatusBadge';
import type {
  TicketListResponse,
  TicketPriority,
  TicketStatus,
} from '../types';

interface TicketsPageProps {
  onSelectTicket: (ticketId: string) => void;
  onCreateTicketClick: () => void;
}

export const TicketsPage: React.FC<TicketsPageProps> = ({
  onSelectTicket,
  onCreateTicketClick,
}) => {
  const [data, setData] = useState<TicketListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [triggeringRunId, setTriggeringRunId] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const fetchTickets = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listTickets({
        page,
        size: pageSize,
        status: (statusFilter as TicketStatus) || '',
        priority: (priorityFilter as TicketPriority) || '',
        category: categoryFilter || '',
        q: search || undefined,
      });
      setData(res);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch tickets');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [page, statusFilter, priorityFilter, categoryFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchTickets();
  };

  const handleTriggerRun = async (e: React.MouseEvent, ticketId: string) => {
    e.stopPropagation();
    setTriggeringRunId(ticketId);
    setRunMessage(null);
    try {
      const run = await api.triggerRun(ticketId);
      setRunMessage(`Agent Run queued (ID: ${run.id.slice(0, 8)}). The worker is processing.`);
      await fetchTickets();
    } catch (err: any) {
      if (err instanceof ApiError) {
        alert(`Could not trigger run: ${err.message} (${err.code})`);
      } else {
        alert(`Failed to trigger agent run: ${err.message}`);
      }
    } finally {
      setTriggeringRunId(null);
    }
  };

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
            Ticket Operations Queue
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Browse, filter, and inspect customer tickets and autonomous agent execution traces.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={fetchTickets}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh List"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={onCreateTicketClick} className="rf-btn rf-btn-primary">
            <Plus size={15} />
            <span>Create Ticket</span>
          </button>
        </div>
      </div>

      {runMessage && (
        <div
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.12)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: '8px',
            padding: '12px 16px',
            fontSize: '13px',
            color: '#38bdf8',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{runMessage}</span>
          <button
            onClick={() => setRunMessage(null)}
            className="rf-btn rf-btn-ghost rf-btn-sm"
            style={{ color: '#38bdf8' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div
        className="rf-card"
        style={{
          padding: '16px 20px',
          marginBottom: '20px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '14px',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ flex: '1 1 280px', position: 'relative' }}>
          <Search
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
            type="text"
            className="rf-input"
            style={{ paddingLeft: '38px' }}
            placeholder="Search tickets by subject or body..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          {/* Status Filter */}
          <select
            className="rf-select"
            style={{ width: 'auto', minWidth: '130px' }}
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="processing">Processing</option>
            <option value="needs_information">Needs Info</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="resolved">Resolved</option>
            <option value="escalated">Escalated</option>
          </select>

          {/* Priority Filter */}
          <select
            className="rf-select"
            style={{ width: 'auto', minWidth: '130px' }}
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Priorities</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>

          {/* Category Filter */}
          <select
            className="rf-select"
            style={{ width: 'auto', minWidth: '140px' }}
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Categories</option>
            <option value="billing">Billing</option>
            <option value="shipping">Shipping</option>
            <option value="refund">Refund</option>
            <option value="technical">Technical</option>
            <option value="account">Account</option>
            <option value="general">General</option>
            <option value="security">Security</option>
            <option value="other">Other</option>
          </select>

          {(statusFilter || priorityFilter || categoryFilter || search) && (
            <button
              onClick={() => {
                setStatusFilter('');
                setPriorityFilter('');
                setCategoryFilter('');
                setSearch('');
                setPage(1);
              }}
              className="rf-btn rf-btn-ghost rf-btn-sm"
              style={{ color: '#94a3b8' }}
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Main Table or Loading/Empty */}
      {loading && !data ? (
        <LoadingSpinner message="Fetching ticket records..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={fetchTickets} />
      ) : !data || data.items.length === 0 ? (
        <div
          className="rf-card"
          style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}
        >
          <TicketIcon size={40} style={{ opacity: 0.4, marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            No tickets match your query
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 18px' }}>
            {statusFilter || priorityFilter || categoryFilter || search
              ? 'Try adjusting your filters or search keywords.'
              : 'Create a ticket using the button below to test the full agent workflow.'}
          </p>
          <button onClick={onCreateTicketClick} className="rf-btn rf-btn-primary">
            <Plus size={15} />
            <span>Create New Ticket</span>
          </button>
        </div>
      ) : (
        <div className="rf-card" style={{ padding: '0', overflow: 'hidden' }}>
          <div className="rf-table-container" style={{ border: 'none', borderRadius: '0' }}>
            <table className="rf-table">
              <thead>
                <tr>
                  <th style={{ width: '38%' }}>Ticket Subject & Details</th>
                  <th>Status</th>
                  <th>Priority</th>
                  <th>Category</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((t) => (
                  <tr
                    key={t.id}
                    onClick={() => onSelectTicket(t.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>
                      <div style={{ fontWeight: 600, color: '#f8fafc', fontSize: '14px' }}>
                        {t.subject}
                      </div>
                      <div
                        style={{
                          fontSize: '12px',
                          color: '#94a3b8',
                          marginTop: '3px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          maxWidth: '460px',
                        }}
                      >
                        {t.body}
                      </div>
                      <div
                        style={{
                          fontSize: '11px',
                          color: '#64748b',
                          fontFamily: 'var(--font-mono)',
                          marginTop: '4px',
                        }}
                      >
                        ID: {t.id.slice(0, 8)} • Requester: {t.requester_email || 'anonymous'}
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
                          color: '#cbd5e1',
                          textTransform: 'capitalize',
                          backgroundColor: 'var(--color-surface-raised)',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        {t.category || 'unclassified'}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {new Date(t.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '8px',
                        }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        {t.status === 'new' || t.status === 'needs_information' ? (
                          <button
                            onClick={(e) => handleTriggerRun(e, t.id)}
                            className="rf-btn rf-btn-primary rf-btn-sm"
                            disabled={triggeringRunId === t.id}
                            title="Run autonomous agent on this ticket"
                          >
                            <Play size={12} />
                            <span>{triggeringRunId === t.id ? 'Starting...' : 'Run Agent'}</span>
                          </button>
                        ) : null}
                        <button
                          onClick={() => onSelectTicket(t.id)}
                          className="rf-btn rf-btn-secondary rf-btn-sm"
                        >
                          Inspect
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer */}
          <div
            style={{
              padding: '14px 20px',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--color-surface-raised)',
            }}
          >
            <div style={{ fontSize: '12px', color: '#94a3b8' }}>
              Showing {data.items.length} of {data.total} ticket{data.total === 1 ? '' : 's'} (Page{' '}
              {data.page} of {Math.max(1, data.pages)})
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="rf-btn rf-btn-secondary rf-btn-sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                <ChevronLeft size={14} />
                <span>Previous</span>
              </button>
              <button
                className="rf-btn rf-btn-secondary rf-btn-sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= data.pages}
              >
                <span>Next</span>
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
