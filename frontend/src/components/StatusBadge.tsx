import React from 'react';
import type { TicketPriority, TicketStatus } from '../types';

interface StatusBadgeProps {
  status: TicketStatus | string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = 'sm' }) => {
  const normalized = status.toLowerCase();
  let badgeClass = 'rf-badge-new';
  let label = status.replace(/_/g, ' ');

  switch (normalized) {
    case 'new':
      badgeClass = 'rf-badge-new';
      break;
    case 'processing':
    case 'running':
      badgeClass = 'rf-badge-processing';
      break;
    case 'needs_information':
      badgeClass = 'rf-badge-needs_information';
      break;
    case 'pending_approval':
    case 'awaiting_approval':
    case 'pending':
      badgeClass = 'rf-badge-pending_approval';
      break;
    case 'resolved':
    case 'completed':
    case 'approved':
      badgeClass = 'rf-badge-resolved';
      break;
    case 'escalated':
    case 'failed':
    case 'rejected':
      badgeClass = 'rf-badge-escalated';
      break;
    default:
      badgeClass = 'rf-badge-new';
  }

  const dotColor =
    normalized === 'resolved' || normalized === 'completed' || normalized === 'approved'
      ? '#34d399'
      : normalized === 'pending_approval' || normalized === 'pending'
      ? '#fbbf24'
      : normalized === 'escalated' || normalized === 'failed' || normalized === 'rejected'
      ? '#f87171'
      : normalized === 'processing' || normalized === 'running'
      ? '#38bdf8'
      : '#94a3b8';

  return (
    <span
      className={`rf-badge ${badgeClass}`}
      style={{
        fontSize: size === 'sm' ? '11px' : '12px',
        padding: size === 'sm' ? '2px 8px' : '4px 10px',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: dotColor,
          display: 'inline-block',
        }}
      />
      {label}
    </span>
  );
};

interface PriorityBadgeProps {
  priority: TicketPriority | string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority }) => {
  const p = priority.toLowerCase();
  let color = '#94a3b8';
  let bg = 'rgba(148, 163, 184, 0.12)';
  let border = 'rgba(148, 163, 184, 0.25)';

  if (p === 'urgent') {
    color = '#f87171';
    bg = 'rgba(248, 113, 113, 0.15)';
    border = 'rgba(248, 113, 113, 0.35)';
  } else if (p === 'high') {
    color = '#fb923c';
    bg = 'rgba(251, 146, 60, 0.15)';
    border = 'rgba(251, 146, 60, 0.35)';
  } else if (p === 'medium') {
    color = '#38bdf8';
    bg = 'rgba(56, 189, 248, 0.15)';
    border = 'rgba(56, 189, 248, 0.3)';
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 8px',
        borderRadius: '4px',
        fontSize: '11px',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        color,
        backgroundColor: bg,
        border: `1px solid ${border}`,
      }}
    >
      {priority}
    </span>
  );
};
