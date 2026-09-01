const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
const HEALTH_URL = import.meta.env.VITE_HEALTH_URL || "http://localhost:8000/health";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let errorData: unknown;
      try {
        errorData = await response.json();
      } catch {
        errorData = await response.text();
      }
      const message =
        typeof errorData === "object" && errorData !== null && "detail" in errorData
          ? String((errorData as { detail: unknown }).detail)
          : `HTTP error! status: ${response.status}`;
      throw new ApiError(message, response.status, errorData);
    }

    if (response.status === 204) {
      return null as unknown as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error instanceof Error ? error.message : "Network error or API unreachable",
      0
    );
  }
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, string | number | boolean | undefined>) => {
    let url = endpoint;
    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += `${url.includes("?") ? "&" : "?"}${queryString}`;
      }
    }
    return request<T>(url, { method: "GET" });
  },

  post: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, {
      method: "DELETE",
    }),

  checkHealth: async (): Promise<{ status: string; service: string }> => {
    try {
      const res = await fetch(HEALTH_URL);
      if (!res.ok) throw new Error("Health check failed");
      return await res.json();
    } catch {
      return { status: "offline", service: "locus-forensic-engine" };
    }
  },
};
