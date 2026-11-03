/**
 * TruthLens API TypeScript Interfaces
 * Corresponds to backend schemas in app/api/schemas.py, app/evaluation/models.py, and app/reporting/export.py
 */

export interface HealthResponse {
  status: "healthy" | "degraded" | string;
  version: string;
  database: "connected" | "disconnected" | string;
}

export interface ProviderItem {
  provider: string;
  configured: boolean;
  key_preview: string | null;
  model: string | null;
  adapter_available: boolean;
  setup_hint: string;
}

export interface ProvidersResponse {
  providers: ProviderItem[];
}

export interface SourceInput {
  id?: string;
  text: string;
  title?: string;
  url?: string;
}

export type VerifierType = "rule_based" | "mock" | "llm";

export interface VerifierConfigInput {
  verifier_type: VerifierType;
  max_concurrency?: number;
  mock_responses?: string[];
  provider_id?: string;
  model_id?: string;
}

export interface EvaluationCreateRequest {
  question: string;
  answer: string;
  sources: SourceInput[];
  config?: VerifierConfigInput;
}

export interface EvaluationMetricsSummary {
  total_claims: number;
  supported: number;
  contradicted: number;
  insufficient_evidence: number;
  errors: number;
}

export interface EvaluationSummary {
  run_id: string;
  created_at: string;
  status: "completed" | "completed_with_errors" | "failed" | string;
  question: string;
  metrics: EvaluationMetricsSummary;
  config: Record<string, unknown>;
}

export interface EvaluationListResponse {
  total: number;
  offset: number;
  limit: number;
  items: EvaluationSummary[];
}

export interface Evidence {
  source_id: string;
  excerpt: string;
  start: number;
  end: number;
}

export type VerificationClassification =
  | "SUPPORTED"
  | "CONTRADICTED"
  | "INSUFFICIENT_EVIDENCE";

export type VerificationStatus = "CLASSIFIED" | "ERROR";

export interface Verification {
  claim_id: string;
  status: VerificationStatus;
  classification: VerificationClassification | null;
  supporting: Evidence[];
  contradicting: Evidence[];
  reasoning: string;
  confidence: number | null;
  conflict: boolean;
  error: string | null;
  method: string;
}

export interface Claim {
  id: string;
  text: string;
  position: number;
}

export interface SkippedSegment {
  text: string;
  position: number;
  reason: string;
}

export interface Ratio {
  numerator: number;
  denominator: number;
  value: number | null;
}

export interface Metrics {
  total_claims: number;
  supported: number;
  contradicted: number;
  insufficient_evidence: number;
  errors: number;
  conflicts: number;
  supported_claim_rate: Ratio;
  evidence_coverage: Ratio;
  verification_completion_rate: Ratio;
}

export interface EvaluationReport {
  run_id: string;
  created_at: string;
  status: "completed" | "completed_with_errors" | "failed" | string;
  question: string;
  answer: string;
  sources: Array<{
    id: string;
    text: string;
    title: string | null;
    url: string | null;
  }>;
  claims: Claim[];
  skipped: SkippedSegment[];
  verifications: Verification[];
  metrics: Metrics;
  config: {
    extractor: string;
    verifier: string;
    max_concurrency: number;
  };
  stages: Array<{ stage: string; state: string }>;
  limitations: string[];
  metric_definitions?: Record<string, string>;
}
