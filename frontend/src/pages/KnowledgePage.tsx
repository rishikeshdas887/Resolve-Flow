import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ErrorAlert, LoadingSpinner } from '../components/Feedback';
import { StatusBadge } from '../components/StatusBadge';
import type { KnowledgeChunk, KnowledgeDocument, User } from '../types';

interface KnowledgePageProps {
  currentUser: User | null;
}

export const KnowledgePage: React.FC<KnowledgePageProps> = ({ currentUser }) => {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Upload modal / form state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const docs = await api.listKnowledgeDocuments();
      setDocuments(docs);
      if (selectedDoc) {
        const found = docs.find((d) => d.id === selectedDoc.id);
        if (found) {
          setSelectedDoc(found);
          loadChunks(found.id);
        } else if (docs.length > 0) {
          setSelectedDoc(docs[0]);
          loadChunks(docs[0].id);
        } else {
          setSelectedDoc(null);
          setChunks([]);
        }
      } else if (docs.length > 0) {
        setSelectedDoc(docs[0]);
        loadChunks(docs[0].id);
      }
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err?.message || 'Failed to fetch knowledge documents');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadChunks = async (docId: string) => {
    setLoadingChunks(true);
    try {
      const c = await api.getKnowledgeChunks(docId);
      setChunks(c);
    } catch (err) {
      console.warn('Could not load document chunks', err);
    } finally {
      setLoadingChunks(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleSelectDoc = (doc: KnowledgeDocument) => {
    setSelectedDoc(doc);
    loadChunks(doc.id);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    // Check size limit: 1MB
    if (uploadFile.size > 1048576) {
      setUploadError('File exceeds 1MB limit enforced by backend.');
      return;
    }

    setUploading(true);
    setUploadError(null);
    try {
      const created = await api.uploadKnowledgeDocument(uploadFile);
      setShowUploadModal(false);
      setUploadFile(null);
      await fetchDocuments();
      setSelectedDoc(created);
      loadChunks(created.id);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setUploadError(err.message);
      } else {
        setUploadError(err?.message || 'Failed to upload document');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleReprocess = async (docId: string) => {
    setReprocessingId(docId);
    try {
      await api.reprocessKnowledgeDocument(docId);
      await fetchDocuments();
    } catch (err: any) {
      alert(`Could not reprocess document: ${err.message}`);
    } finally {
      setReprocessingId(null);
    }
  };

  const handleDelete = async (docId: string) => {
    if (currentUser?.role !== 'admin') {
      alert('Forbidden: Document deletion requires the admin role.');
      return;
    }

    if (!confirm('Are you sure you want to delete this knowledge document and all its chunks?')) {
      return;
    }

    setDeletingId(docId);
    try {
      await api.deleteKnowledgeDocument(docId);
      await fetchDocuments();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    } finally {
      setDeletingId(null);
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
            Grounding Knowledge Base
          </h1>
          <p style={{ fontSize: '13px', color: '#94a3b8' }}>
            Evidence documents ingested, vector-embedded in PGVector, and cited during agent resolution.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={fetchDocuments}
            className="rf-btn rf-btn-secondary"
            disabled={loading}
            title="Refresh Knowledge Base"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setShowUploadModal(true)} className="rf-btn rf-btn-primary">
            <Upload size={14} />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {loading && documents.length === 0 ? (
        <LoadingSpinner message="Fetching knowledge documents..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={fetchDocuments} />
      ) : documents.length === 0 ? (
        <div
          className="rf-card"
          style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}
        >
          <BookOpen size={40} style={{ opacity: 0.4, marginBottom: '12px' }} />
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px' }}>
            No knowledge documents found
          </h3>
          <p style={{ fontSize: '13px', maxWidth: '420px', margin: '0 auto 16px' }}>
            Upload standard operating procedures (.md or .txt) so the agent can cite authentic evidence.
          </p>
          <button onClick={() => setShowUploadModal(true)} className="rf-btn rf-btn-primary">
            <Upload size={14} />
            <span>Upload First Document</span>
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
          {/* Left Column: Documents List */}
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
              Ingested Documents ({documents.length})
            </div>

            {documents.map((doc) => {
              const isSelected = selectedDoc?.id === doc.id;
              return (
                <div
                  key={doc.id}
                  onClick={() => handleSelectDoc(doc)}
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
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#f8fafc' }}>
                      {doc.title}
                    </div>
                    <StatusBadge status={doc.status} size="sm" />
                  </div>

                  <div
                    style={{
                      fontSize: '12px',
                      color: '#94a3b8',
                      marginBottom: '8px',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {doc.source_uri || 'Document'} • {doc.doc_type || 'markdown'}
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
                    <span>{doc.checksum ? `Checksum: ${doc.checksum.slice(0, 8)}` : 'PGVector Ready'}</span>
                    <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Selected Document Inspector & Chunks */}
          {selectedDoc ? (
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
                    {selectedDoc.title}
                  </h2>
                  <div
                    style={{
                      fontSize: '12px',
                      color: '#94a3b8',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    ID: {selectedDoc.id} • {selectedDoc.source_uri || selectedDoc.doc_type}
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    onClick={() => handleReprocess(selectedDoc.id)}
                    className="rf-btn rf-btn-secondary rf-btn-sm"
                    disabled={reprocessingId === selectedDoc.id}
                    title="Recompute chunks and vector embeddings"
                  >
                    <RefreshCw size={13} className={reprocessingId === selectedDoc.id ? 'spin' : ''} />
                    <span>{reprocessingId === selectedDoc.id ? 'Reprocessing...' : 'Reprocess'}</span>
                  </button>

                  {isAdmin && (
                    <button
                      onClick={() => handleDelete(selectedDoc.id)}
                      className="rf-btn rf-btn-danger rf-btn-sm"
                      disabled={deletingId === selectedDoc.id}
                      title="Delete document and chunks"
                    >
                      <Trash2 size={13} />
                      <span>{deletingId === selectedDoc.id ? 'Deleting...' : 'Delete'}</span>
                    </button>
                  )}
                </div>
              </div>

              {selectedDoc.error && (
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: '8px',
                    padding: '12px 14px',
                    color: '#f87171',
                    fontSize: '13px',
                    marginBottom: '20px',
                  }}
                >
                  {selectedDoc.error}
                </div>
              )}

              {/* Chunks Inspector */}
              <div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                    Vector Embeddings & Chunks ({chunks.length})
                  </div>
                  <span style={{ fontSize: '11px', color: '#64748b' }}>
                    Embedded in PGVector store for semantic retrieval
                  </span>
                </div>

                {loadingChunks ? (
                  <LoadingSpinner message="Loading chunk records..." size="sm" />
                ) : chunks.length === 0 ? (
                  <div
                    style={{
                      padding: '24px',
                      textAlign: 'center',
                      backgroundColor: 'var(--color-surface-raised)',
                      borderRadius: '8px',
                      color: '#64748b',
                      fontSize: '13px',
                    }}
                  >
                    No chunks available for this document.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {chunks.map((c) => (
                      <div
                        key={c.id}
                        style={{
                          backgroundColor: 'var(--color-surface-raised)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: '8px',
                          padding: '12px 16px',
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
                              fontSize: '11px',
                              fontWeight: 600,
                              color: 'var(--primary-400)',
                              fontFamily: 'var(--font-mono)',
                            }}
                          >
                            Chunk #{c.chunk_index} ({c.id.slice(0, 8)})
                          </span>
                          <span style={{ fontSize: '11px', color: '#64748b' }}>
                            {c.token_count} tokens
                          </span>
                        </div>
                        <div
                          style={{
                            backgroundColor: 'var(--color-canvas)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '4px',
                            padding: '10px 12px',
                            fontSize: '12px',
                            color: '#cbd5e1',
                            lineHeight: 1.5,
                            whiteSpace: 'pre-wrap',
                          }}
                        >
                          {c.content}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="rf-modal-backdrop" onClick={() => setShowUploadModal(false)}>
          <div className="rf-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="rf-modal-header">
              <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#f8fafc' }}>
                Upload Grounding Knowledge Document
              </h2>
            </div>
            <form onSubmit={handleUploadSubmit}>
              <div className="rf-modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ fontSize: '13px', color: '#94a3b8' }}>
                  Supported formats: <strong>.md, .markdown, .txt</strong> (up to 1MB). Documents will be chunked
                  and indexed into Postgres pgvector.
                </p>

                {uploadError && (
                  <div
                    style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.12)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      borderRadius: '6px',
                      padding: '10px 12px',
                      color: '#f87171',
                      fontSize: '12px',
                    }}
                  >
                    {uploadError}
                  </div>
                )}

                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '12px',
                      fontWeight: 600,
                      color: '#cbd5e1',
                      marginBottom: '6px',
                    }}
                  >
                    Select File (.md / .txt)
                  </label>
                  <input
                    type="file"
                    accept=".md,.markdown,.txt"
                    onChange={(e) => setUploadFile(e.target.files ? e.target.files[0] : null)}
                    className="rf-input"
                    required
                  />
                </div>
              </div>

              <div className="rf-modal-footer">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="rf-btn rf-btn-secondary"
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rf-btn rf-btn-primary"
                  disabled={uploading || !uploadFile}
                >
                  {uploading ? 'Ingesting & Chunking...' : 'Upload & Ingest'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
