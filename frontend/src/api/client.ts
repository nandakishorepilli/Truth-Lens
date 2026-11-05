/**
 * Centralized API client for TruthLens backend.
 * Provides typed HTTP methods and standard error handling.
 */

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// In development, Vite proxy forwards /api to http://127.0.0.1:8000
// If VITE_API_BASE_URL is explicitly set to empty or another domain, respect it.
const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const API_BASE_URL = RAW_BASE_URL !== undefined ? RAW_BASE_URL : "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = API_BASE_URL ? `${API_BASE_URL.replace(/\/$/, "")}${path}` : path;

  let response: Response;
  try {
    response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init?.headers,
      },
      ...init,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, `Cannot connect to TruthLens backend: ${message}`);
  }

  if (!response.ok) {
    let errorDetail: unknown;
    let message = `Request failed with status ${response.status}`;
    try {
      errorDetail = await response.json();
      if (
        typeof errorDetail === "object" &&
        errorDetail !== null &&
        "detail" in errorDetail
      ) {
        const d = (errorDetail as { detail: unknown }).detail;
        message = typeof d === "string" ? d : JSON.stringify(d);
      }
    } catch {
      try {
        message = await response.text();
      } catch {
        // fallback to default
      }
    }
    throw new ApiError(response.status, message, errorDetail);
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) =>
    request<T>(path, { method: "GET", ...init }),
  post: <T>(path: string, body: unknown, init?: RequestInit) =>
    request<T>(path, {
      method: "POST",
      body: JSON.stringify(body),
      ...init,
    }),
};
