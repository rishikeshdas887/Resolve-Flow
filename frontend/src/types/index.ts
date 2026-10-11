// Core TypeScript types matching ResolveFlow OpenAPI contract

export type UserRole = 'customer' | 'support_agent' | 'admin';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type TicketStatus =
  | 'new'
  | 'processing'
  | 'needs_information'
  | 'pending_approval'
  | 'resolved'
  | 'escalated';

export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';

export type TicketCategory =
  | 'billing'
  | 'shipping'
  | 'refund'
  | 'technical'
  | 'account'
  | 'general'
  | 'security'
  | 'other';

export interface Ticket {
  id: string;
  subject: string;
  body: string;
  requester_email: string | null;
  status: TicketStatus;
  priority: TicketPriority;
  category: TicketCategory | null;
  assigned_queue: string | null;
  tags: string[];
  created_by_id: string | null;
  assigned_to_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface TicketListResponse {
  items: Ticket[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface TicketCreatePayload {
  subject: string;
  body: string;
  requester_email?: string;
  priority?: TicketPriority;
  category?: TicketCategory;
  assigned_queue?: string;
  tags?: string[];
}

export interface TicketUpdatePayload {
  subject?: string;
  body?: string;
  priority?: TicketPriority;
  assigned_queue?: string;
}

export type RunStatus = 'queued' | 'running' | 'awaiting_approval' | 'completed' | 'failed';

export type RunDisposition =
  | 'resolved'
  | 'needs_information'
  | 'pending_approval'
  | 'escalated'
  | 'failed';

export interface AgentRun {
  id: string;
  ticket_id: string;
  status: RunStatus;
  disposition: RunDisposition | null;
  provider: string;
  attempt: number;
  max_attempts: number;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
  summary: string | null;
}

export type RetrievalMode = 'vector' | 'lexical';

export interface EvidenceItem {
  id: string;
  chunk_id: string;
  document_id: string;
  document_title: string;
  score: number;
  excerpt: string;
  retrieval_mode: RetrievalMode;
}

export type PolicyDecision = 'allow' | 'deny' | 'require_approval';

export type ProposalActionStatus =
  | 'proposed'
  | 'pending_approval'
  | 'executed'
  | 'rejected'
  | 'failed';

export interface ProposalAction {
  id: string;
  action_type: string;
  params: Record<string, any>;
  status: ProposalActionStatus;
  policy_decision: PolicyDecision;
  policy_reasons: string[];
  draft_response: string | null;
  cited_evidence_ids: string[];
  result: Record<string, any> | null;
  executed_at: string | null;
  is_terminal: boolean;
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface ApprovalRequest {
  id: string;
  ticket_id: string;
  run_id: string;
  action_id: string;
  status: ApprovalStatus;
  reason: string;
  reviewer_id: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
  action?: ProposalAction;
  run?: AgentRun;
  ticket?: Ticket;
}

export interface TicketEvent {
  id: string;
  ticket_id: string;
  event_type: string;
  detail: Record<string, any>;
  actor_type: string;
  actor_id: string | null;
  run_id: string | null;
  created_at: string;
}

export interface StatusHistoryItem {
  id: string;
  ticket_id: string;
  from_status: TicketStatus | null;
  to_status: TicketStatus;
  reason: string | null;
  changed_by_id: string | null;
  created_at: string;
}

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed';

export interface KnowledgeDocument {
  id: string;
  title: string;
  source_uri?: string | null;
  doc_type?: string;
  status: DocumentStatus;
  checksum?: string;
  error?: string | null;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  created_at: string;
}

export interface DashboardSummary {
  tickets_total: number;
  tickets_by_status: Record<string, number>;
  tickets_by_priority: Record<string, number>;
  tickets_by_category: Record<string, number>;
  open_tickets: number;
  runs_total: number;
  runs_by_status: Record<string, number>;
  runs_completed_24h: number;
  avg_run_duration_ms: number | null;
  pending_approvals: number;
  resolved_tickets: number;
  resolution_rate: number | null;
  knowledge_documents: number;
  knowledge_chunks: number;
}

export interface EvalSummary {
  dataset_size: number;
  passed: number;
  failed: number;
  pass_rate: number;
  provider: string;
  mode: string;
  avg_latency_ms?: number;
}

export interface EvalCaseResult {
  case_id: string;
  passed: boolean;
  expected: Record<string, any> | string;
  actual: Record<string, any> | string;
  detail?: string | null;
  latency_ms?: number;
}

export interface EvalRun {
  id: string;
  dataset_name: string;
  provider: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  summary?: EvalSummary;
  results?: EvalCaseResult[] | null;
  created_at?: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    correlation_id?: string;
  };
}
