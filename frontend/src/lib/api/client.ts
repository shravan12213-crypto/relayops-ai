/**
 * RelayOps API Client
 * Strict typed fetch wrapper with error envelope extraction and cookie authentication.
 */

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.details = payload.details ?? {};
  }
}

// Global 401 callback for redirecting or notifying the auth state
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
}

function humanizeMessage(status: number, message?: string): string {
  if (
    message &&
    message.trim() &&
    !message.startsWith("Internal Server Error") &&
    !message.startsWith("Request failed with status") &&
    !message.startsWith("HTTP_ERROR")
  ) {
    return message;
  }
  switch (status) {
    case 401:
      return "Your session has expired. Please log in again to continue.";
    case 403:
      return "Access restricted: You do not have the role or security clearance required for this action.";
    case 404:
      return "The requested record was not found. It may have been moved or deleted.";
    case 409:
      return "Concurrent update detected: another user modified this record. Please refresh to load the latest changes.";
    case 422:
      return "Validation error: please verify your input values and try again.";
    case 429:
      return "Rate limit exceeded: too many requests. Please wait a moment before trying again.";
    case 500:
      return "An unexpected server error occurred. Please try again or check the system audit log.";
    case 502:
    case 503:
    case 504:
      return "Unable to reach the RelayOps backend. Please verify the API server is active.";
    default:
      return message || `Request failed (HTTP ${status}). Please try again.`;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { error?: ApiErrorPayload };
    if (body.error) {
      return new ApiError(response.status, {
        code: body.error.code,
        message: humanizeMessage(response.status, body.error.message),
        details: body.error.details,
      });
    }
  } catch {
    // Non-JSON error body (proxy failure, HTML error page)
  }
  return new ApiError(response.status, {
    code: "HTTP_ERROR",
    message: humanizeMessage(response.status, response.statusText),
  });
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  // Auto-set Content-Type for JSON body
  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...options,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const error = await toApiError(response);
    if (response.status === 401 && !path.includes("/auth/login") && !path.includes("/auth/me")) {
      if (unauthorizedHandler) {
        unauthorizedHandler();
      }
    }
    throw error;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "GET", signal });
}

export function apiPost<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body !== undefined ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
    signal,
  });
}

export function apiPatch<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
}

export function apiPut<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
}

export function apiDelete<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "DELETE", signal });
}
