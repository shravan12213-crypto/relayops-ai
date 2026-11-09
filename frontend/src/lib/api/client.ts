/** Minimal typed fetch wrapper that understands the backend's error envelope. */

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

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { error?: ApiErrorPayload };
    if (body.error) {
      return new ApiError(response.status, body.error);
    }
  } catch {
    // Non-JSON error body (proxy failure, HTML error page): fall through.
  }
  return new ApiError(response.status, {
    code: "HTTP_ERROR",
    message: response.statusText || `Request failed with status ${response.status}`,
  });
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    credentials: "include",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as T;
}
