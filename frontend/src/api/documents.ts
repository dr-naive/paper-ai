import request from './index'

export interface DocumentRevision { id: string; document_id: string; version: number; content_json: Record<string, any>; created_by: string; source_execution_id?: string | null; created_at: string }
export interface WritingDocument { id: string; project_id: string; title: string; document_type: string; status: string; current_revision_id?: string | null; current_revision?: DocumentRevision | null; created_at: string; updated_at: string }
export interface AIEditProposal { document_id: string; base_revision_id: string; action: string; range: { from: number; to: number }; original: string; replacement: string; status: 'proposal'; message: string }
export interface CitationAuditIssue { citation_index: number; severity: 'warning' | 'error'; code: string; message: string; claim_excerpt?: string }
export interface CitationVerificationResult { citation_key: string; paper_id: string; evidence_id: string; status: 'verified' | 'weak' | 'unsupported'; code: string; reason: string; confidence?: number | null; claim_text: string; original_claim: string; adjusted_claim?: string | null; adjustment_applied: boolean; evidence_snippet: string }
export interface CitationAudit { document_id: string; revision_id?: string | null; citation_count: number; linked_evidence_count: number; issue_count: number; issues: CitationAuditIssue[]; citation_results: CitationVerificationResult[]; passed: boolean }
export interface WritingCitationMapping { citation_key: string; paper_id: string; evidence_id: string; claim_text: string }
export interface WritingRewriteRequest { document_id: string; instruction: string; selected_text: string; selection_from: number; selection_to: number; section_path: string[]; nearby_text?: string | null; base_revision_id?: string | null; citations?: WritingCitationMapping[] }
export interface WritingRewriteProposal { proposal_id: string; project_id: string; document_id: string; base_revision_id: string; kind: 'rewrite'; status: 'ready' | 'partially_verified' | 'verification_failed'; content: string; original_content: string; citations: CitationVerificationResult[]; warnings: string[]; selection: { from: number; to: number }; section_path: string[] }
export type WritingCitationStyle = 'gbt7714' | 'apa' | 'ieee'
export interface WritingGenerateRequest { document_id: string; instruction: string; section_path: string[]; nearby_text?: string | null; citation_style?: WritingCitationStyle; base_revision_id?: string | null }
export interface WritingGenerationProposal { proposal_id: string; project_id: string; document_id: string; base_revision_id: string; kind: 'generate'; status: 'ready' | 'partially_verified' | 'verification_failed'; content: string; citations: CitationVerificationResult[]; warnings: string[]; section_path: string[]; citation_style: WritingCitationStyle }

export const listDocuments = (projectId: string) => request.get<{ items: WritingDocument[] }>(`/api/v1/projects/${projectId}/documents`)
export const createDocument = (projectId: string, data: { title: string; document_type?: string; content_json?: Record<string, any> }) => request.post<WritingDocument>(`/api/v1/projects/${projectId}/documents`, data)
export const getDocument = (documentId: string) => request.get<WritingDocument>(`/api/v1/documents/${documentId}`)
export const updateDocument = (documentId: string, data: { title?: string; status?: string }) => request.patch<WritingDocument>(`/api/v1/documents/${documentId}`, data)
export const listRevisions = (documentId: string) => request.get<{ items: DocumentRevision[] }>(`/api/v1/documents/${documentId}/revisions`)
export const createRevision = (documentId: string, data: { content_json: Record<string, any>; created_by?: string; source_execution_id?: string }) => request.post<DocumentRevision>(`/api/v1/documents/${documentId}/revisions`, data)
export const proposeAIEdit = (documentId: string, data: { action: string; selected_text: string; from_pos: number; to_pos: number }) => request.post<AIEditProposal>(`/api/v1/documents/${documentId}/ai-actions`, data)
export const rewriteSelection = (projectId: string, data: WritingRewriteRequest) => request.post<WritingRewriteProposal>(`/api/v1/projects/${projectId}/writing/agent/rewrite`, data)
export const generateParagraph = (projectId: string, data: WritingGenerateRequest) => request.post<WritingGenerationProposal>(`/api/v1/projects/${projectId}/writing/agent/generate`, data)
export const auditCitations = (documentId: string) => request.post<CitationAudit>(`/api/v1/documents/${documentId}/citation-audit`)
