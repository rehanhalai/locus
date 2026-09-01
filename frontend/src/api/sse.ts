const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export interface SSEOptions<T = unknown> {
  onMessage: (data: T) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

/**
 * Subscribes to an SSE endpoint using EventSource with automatic cleanup.
 */
export function subscribeSSE<T = Record<string, unknown>>(
  endpoint: string,
  options: SSEOptions<T>
): () => void {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data) as T;
      options.onMessage(parsed);

      const status =
        (parsed as { status?: string; stage?: string }).status ||
        (parsed as { status?: string; stage?: string }).stage;

      if (
        status === "DONE" ||
        status === "COMPLETED" ||
        status === "FAILED" ||
        status === "ERROR"
      ) {
        eventSource.close();
        if (options.onComplete) {
          options.onComplete();
        }
      }
    } catch {
      // Non-JSON raw event
      options.onMessage(event.data as unknown as T);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    if (options.onError) {
      options.onError(new Error("SSE connection failed or stream terminated"));
    }
  };

  return () => {
    eventSource.close();
  };
}
