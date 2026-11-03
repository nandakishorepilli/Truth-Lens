import { api, API_BASE_URL } from "./client";
import type {
  EvaluationCreateRequest,
  EvaluationListResponse,
  EvaluationReport,
  HealthResponse,
  ProvidersResponse,
} from "./types";

export const getHealth = (): Promise<HealthResponse> =>
  api.get<HealthResponse>("/api/health");

export const getProviders = (): Promise<ProvidersResponse> =>
  api.get<ProvidersResponse>("/api/providers");

export const createEvaluation = (
  payload: EvaluationCreateRequest
): Promise<EvaluationReport> =>
  api.post<EvaluationReport>("/api/evaluations", payload);

export const listEvaluations = (
  limit = 50,
  offset = 0
): Promise<EvaluationListResponse> =>
  api.get<EvaluationListResponse>(
    `/api/evaluations?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`
  );

export const getEvaluation = (runId: string): Promise<EvaluationReport> =>
  api.get<EvaluationReport>(`/api/evaluations/${encodeURIComponent(runId)}`);

export const getExportUrl = (runId: string, format: "json" | "csv"): string => {
  const base = API_BASE_URL ? API_BASE_URL.replace(/\/$/, "") : "";
  return `${base}/api/evaluations/${encodeURIComponent(runId)}/export?format=${format}`;
};
