// ResolveFlow API Client
import type {
  AgentRun,
  ApprovalRequest,
  DashboardSummary,
  EvidenceItem,
  KnowledgeChunk,
  KnowledgeDocument,
  LoginResponse,
  ProposalAction,
  StatusHistoryItem,
  Ticket,
  TicketCreatePayload,
  TicketEvent,
  TicketListResponse,
  TicketPriority,
  TicketStatus,
  TicketUpdatePayload,
  User,
  UserRole,
} from '../types';

export class ApiError extends Error {
  public code: string;
  public details?: Record<string, any>;
  public correlationId?: string;
  public status: number;

  constructor(status: number, code: string, message: string, details?: Record<string, any>, correlationId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.correlationId = correlationId;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const TOKEN_KEY = 'resolveflow_token';
const USER_KEY = 'resolveflow_user';

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  public getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  public setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  public clearAuth(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  public getStoredUser(): User | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  }

  public setStoredUser(user: User): void {
    localStorage.setItem(USER_KEY, jsonStringify(user));
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has('Accept')) {
      headers.set('Accept', 'application/json');
    }

    const token = this.getToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const res = await fetch(url, { ...options, headers });

    if (res.status === 204) {
      return null as unknown as T;
    }

    const contentType = res.headers.get('content-type') || '';
    let data: any = null;
    if (contentType.includes('application/json')) {
      data = await res.json();
    } else {
      data = await res.text();
    }

    if (!res.ok) {
      if (data && typeof data === 'object' && data.error) {
        throw new ApiError(
          res.status,
          data.error.code || 'unknown_error',
          data.error.message || `Request failed with status ${res.status}`,
          data.error.details,
          data.error.correlation_id
        );
      }
      throw new ApiError(
        res.status,
        'http_error',
        typeof data === 'string' && data ? data : `Request failed with HTTP ${res.status}`
      );
    }

    return data as T;
  }

  // Auth endpoints
  public async login(email: string, password: string): Promise<LoginResponse> {
    const res = await this.request<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    this.setToken(res.access_token);
    this.setStoredUser(res.user);
    return res;
  }

  public async getMe(): Promise<User> {
    const user = await this.request<User>('/api/v1/auth/me');
    this.setStoredUser(user);
    return user;
  }

  public async createUser(data: {
    email: string;
    role: UserRole;
    full_name?: string;
    password?: string;
  }): Promise<User> {
    return this.request<User>('/api/v1/auth/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  // Dashboard endpoints
  public async getDashboardSummary(): Promise<DashboardSummary> {
    return this.request<DashboardSummary>('/api/v1/dashboard/summary');
  }

  // Ticket endpoints
  public async listTickets(params: {
    page?: number;
    size?: number;
    status?: TicketStatus | '';
    priority?: TicketPriority | '';
    category?: string | '';
    q?: string;
  } = {}): Promise<TicketListResponse> {
    const query = new URLSearchParams();
    if (params.page !== undefined) query.set('page', String(params.page));
    if (params.size !== undefined) query.set('size', String(params.size));
    if (params.status) query.set('status', params.status);
    if (params.priority) query.set('priority', params.priority);
    if (params.category) query.set('category', params.category);
    if (params.q) query.set('q', params.q);

    const queryString = query.toString();
    const endpoint = `/api/v1/tickets${queryString ? `?${queryString}` : ''}`;
    return this.request<TicketListResponse>(endpoint);
  }

  public async getTicket(ticketId: string): Promise<Ticket> {
    return this.request<Ticket>(`/api/v1/tickets/${ticketId}`);
  }

  public async createTicket(payload: TicketCreatePayload, idempotencyKey?: string): Promise<Ticket> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    headers['Idempotency-Key'] = idempotencyKey || crypto.randomUUID();

    return this.request<Ticket>('/api/v1/tickets', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  }

  public async updateTicket(ticketId: string, payload: TicketUpdatePayload): Promise<Ticket> {
    return this.request<Ticket>(`/api/v1/tickets/${ticketId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  public async getTicketEvents(ticketId: string): Promise<TicketEvent[]> {
    const res = await this.request<any>(`/api/v1/tickets/${ticketId}/events`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getTicketStatusHistory(ticketId: string): Promise<StatusHistoryItem[]> {
    const res = await this.request<any>(`/api/v1/tickets/${ticketId}/status-history`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getTicketRuns(ticketId: string): Promise<AgentRun[]> {
    const res = await this.request<any>(`/api/v1/tickets/${ticketId}/runs`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async triggerRun(ticketId: string, idempotencyKey?: string): Promise<AgentRun> {
    const headers: Record<string, string> = {};
    headers['Idempotency-Key'] = idempotencyKey || crypto.randomUUID();

    return this.request<AgentRun>(`/api/v1/tickets/${ticketId}/runs`, {
      method: 'POST',
      headers,
    });
  }

  // Run details endpoints
  public async getRun(runId: string): Promise<AgentRun> {
    return this.request<AgentRun>(`/api/v1/runs/${runId}`);
  }

  public async getRunEvidence(runId: string): Promise<EvidenceItem[]> {
    const res = await this.request<any>(`/api/v1/runs/${runId}/evidence`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getRunProposal(runId: string): Promise<ProposalAction[]> {
    const res = await this.request<any>(`/api/v1/runs/${runId}/proposal`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  // Approvals endpoints
  public async listApprovals(params: { status?: 'pending' | 'approved' | 'rejected' } = {}): Promise<ApprovalRequest[]> {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    const queryString = query.toString();
    const res = await this.request<any>(`/api/v1/approvals${queryString ? `?${queryString}` : ''}`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getApproval(approvalId: string): Promise<ApprovalRequest> {
    return this.request<ApprovalRequest>(`/api/v1/approvals/${approvalId}`);
  }

  public async approveAction(approvalId: string, decisionNote?: string): Promise<ApprovalRequest> {
    return this.request<ApprovalRequest>(`/api/v1/approvals/${approvalId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: decisionNote || null }),
    });
  }

  public async rejectAction(approvalId: string, decisionNote?: string): Promise<ApprovalRequest> {
    return this.request<ApprovalRequest>(`/api/v1/approvals/${approvalId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: decisionNote || null }),
    });
  }

  // Knowledge base endpoints
  public async listKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
    const res = await this.request<any>('/api/v1/knowledge/documents');
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getKnowledgeDocument(docId: string): Promise<KnowledgeDocument> {
    return this.request<KnowledgeDocument>(`/api/v1/knowledge/documents/${docId}`);
  }

  public async getKnowledgeChunks(docId: string): Promise<KnowledgeChunk[]> {
    const res = await this.request<any>(`/api/v1/knowledge/documents/${docId}/chunks`);
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async uploadKnowledgeDocument(file: File): Promise<KnowledgeDocument> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request<KnowledgeDocument>('/api/v1/knowledge/documents', {
      method: 'POST',
      body: formData,
    });
  }

  public async reprocessKnowledgeDocument(docId: string): Promise<KnowledgeDocument> {
    return this.request<KnowledgeDocument>(`/api/v1/knowledge/documents/${docId}/reprocess`, {
      method: 'POST',
    });
  }

  public async deleteKnowledgeDocument(docId: string): Promise<void> {
    return this.request<void>(`/api/v1/knowledge/documents/${docId}`, {
      method: 'DELETE',
    });
  }

  // Evals endpoints
  public async listEvalRuns(): Promise<any[]> {
    const res = await this.request<any>('/api/v1/evals/runs');
    return Array.isArray(res) ? res : res?.items || [];
  }

  public async getEvalRun(runId: string): Promise<any> {
    return this.request<any>(`/api/v1/evals/runs/${runId}`);
  }

  public async triggerEvalRun(datasetName: string = 'evals/dataset.jsonl'): Promise<any> {
    return this.request<any>('/api/v1/evals/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset: datasetName }),
    });
  }
}

function jsonStringify(obj: any): string {
  try {
    return JSON.stringify(obj);
  } catch {
    return '';
  }
}

export const api = new ApiClient();
