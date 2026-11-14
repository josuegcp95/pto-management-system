const API_URL = import.meta.env.VITE_API_URL;

export type APIErrorResponse = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};

export class APIError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "APIError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  if (!API_URL) {
    throw new APIError(
      "CONFIGURATION_ERROR",
      "Backend API URL is not configured.",
      0
    );
  }

  const headers = new Headers(options.headers);

  if (options.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_URL.replace(/\/+$/, "")}/${endpoint.replace(/^\/+/, "")}`,
      {
        ...options,
        headers,
      }
    );
  } catch {
    throw new APIError(
      "NETWORK_ERROR",
      "Unable to connect to the server.",
      0
    );
  }

  if (!response.ok) {
    let errorData: APIErrorResponse | null = null;

    try {
      errorData = (await response.json()) as APIErrorResponse;
    } catch {
      // The server did not return valid JSON.
    }

    const error = errorData?.error;

    throw new APIError(
      error?.code ?? "HTTP_ERROR",
      error?.message ?? `Request failed (${response.status}).`,
      response.status,
      error?.details ?? {}
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
