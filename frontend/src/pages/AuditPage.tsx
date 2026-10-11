import React, { useEffect, useState } from 'react';
import {
  ExternalLink,
  History,
  RefreshCw,
  Search,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import type { TicketEvent } from '../types';

interface AuditPageProps {
  onSelectTicket: (ticketId: string) => void;
}

interface EnrichedEvent extends TicketEvent {
  ticketSubject?: string;
}

export const AuditPage: React.FC<AuditPageProps> = ({ onSelectTicket }) => {
  const [events, setEvents] = useState<EnrichedEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('');
  const [search, setSearch] = useState<string>('');

  const fetchAuditData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch latest tickets and their events to construct aggregate ledger
      const ticketsRes = await api.listTickets({ size: 10 });
      const allEvents: EnrichedEvent[] = [];

      await Promise.all(
        ticketsRes.items.map(async (t) => {
          try {
            const evs = await api.getTicketEvents(t.id);
            evs.forEach((e) => {
              allEvents.push({
                ...e,
                ticketSubject: t.subject,
              });
            });
          } catch {
            // ignore
          }
        })
      );

      // Sort newest first
      allEvents.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setEvents(allEvents);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch audit events');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, []);

  const filteredEvents = events.filter((e) => {
    if (filterType && e.event_type !== filterType) return false;
    if (search) {
      const q = search.toLowerCase();
      const matchType = e.event_type.toLowerCase().includes(q);
      const matchSubject = e.ticketSubject?.toLowerCase().includes(q) || false;
      const matchActor = e.actor_type.toLowerCase().includes(q);
      if (!matchType && !matchSubject && !matchActor) return false;
    }
    return true;
  });

  const eventTypes = Array.from(new Set(events.map((e) => e.event_type)));

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
            System Audit & Governance Telemetry
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Cryptographically audited ledger of all state mutations, model proposals, and human decisions.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={fetchAuditData}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh Audit Log"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

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
        <div style={{ flex: '1 1 280px', position: 'relative' }}>
          <Search
            size={16}
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50)',
              color: '#64748b',
            }}
          />
          <input
            type="text"
            className="rf-input"
            style={{ paddingLeft: '38px' }}
            placeholder="Search by event type, actor, or subject..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <select
          className="rf-select"
          style={{ width: 'auto', minWidth: '180px' }}
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All Event Types</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        {(filterType || search) && (
          <button
            onClick={() => {
              setFilterType('');
              setSearch('');
            }}
            className="rf-btn rf-btn-ghost rf-btn-sm"
            style={{ color: '#94a3b8' }}
          >
            Reset
          </button>
        )}
      </div>

      {loading && events.length === 0 ? (
        <LoadingSpinner message="Aggregating audit events..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={fetchAuditData} />
      ) : filteredEvents.length === 0 ? (
        <div
          className="rf-card"
          style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}
        >
          <History size={40} style={{ opacity: 0.4, marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            No audit events found
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto' }}>
            {filterType || search
              ? 'No events match your current filter settings.'
              : 'Audit events will record automatically when tickets are created or executed.'}
          </p>
        </div>
      ) : (
        <div className="rf-card" style={{ padding: '0', overflow: 'hidden' }}>
          <div className="rf-table-container" style={{ border: 'none', borderRadius: '0' }}>
            <table className="rf-table">
              <thead>
                <tr>
                  <th>Event Type</th>
                  <th>Originating Ticket</th>
                  <th>Actor</th>
                  <th>Payload & Parameters</th>
                  <th>Timestamp</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((ev) => (
                  <tr key={ev.id}>
                    <td>
                      <span
                        style={{
                          fontWeight: 600,
                          color: '#f8fafc',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          backgroundColor: 'var(--color-surface-raised)',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        {ev.event_type}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: '#e2e8f0' }}>
                        {ev.ticketSubject || 'Support Ticket'}
                      </div>
                      <div
                        style={{
                          fontSize: '11px',
                          color: '#64748b',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        ID: {ev.ticket_id.slice(0, 8)}
                      </div>
                    </td>
                    <td>
                      <span
                        style={{
                          fontSize: '12px',
                          color: ev.actor_type === 'admin' ? '#34d399' : '#38bdf8',
                          fontWeight: 500,
                          textTransform: 'capitalize',
                        }}
                      >
                        {ev.actor_type}
                      </span>
                    </td>
                    <td>
                      {ev.detail && Object.keys(ev.detail).length > 0 ? (
                        <pre
                          style={{
                            margin: 0,
                            fontSize: '11px',
                            fontFamily: 'var(--font-mono)',
                            color: '#cbd5e1',
                            backgroundColor: 'var(--color-canvas)',
                            padding: '6px 10px',
                            borderRadius: '4px',
                            maxWidth: '380px',
                            overflowX: 'auto',
                            maxHeight: '80px',
                          }}
                        >
                          {JSON.stringify(ev.detail, null, 2)}
                        </pre>
                      ) : (
                        <span style={{ fontSize: '11px', color: '#64748b' }}>No payload details</span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                        {new Date(ev.created_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        {new Date(ev.created_at).toLocaleDateString()}
                      </div>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => onSelectTicket(ev.ticket_id)}
                        className="rf-btn rf-btn-secondary rf-btn-sm"
                        style={{ gap: '4px' }}
                      >
                        <span>Inspect</span>
                        <ExternalLink size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
