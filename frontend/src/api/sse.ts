const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export interface SSEOptions<T = unknown> {
  onMessage: (data: T) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

/**
 * Subscribes to an SSE endpoint using EventSource with automatic reconnection support and safe error extraction.
 */
export function subscribeSSE<T = Record<string, unknown>>(
  endpoint: string,
  options: SSEOptions<T>
): () => void {
  const url = endpoint.startsWith("http") ? endpoint : `${BASE_URL}${endpoint}`;
  const eventSource = new EventSource(url);
  let isClosed = false;

  const closeStream = () => {
    if (!isClosed) {
      isClosed = true;
      eventSource.close();
    }
  };

  eventSource.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data) as T;
      options.onMessage(parsed);

      if (typeof parsed === "object" && parsed !== null) {
        const obj = parsed as Record<string, unknown>;
        const eventType = String(obj.type || "");
        const status = String(obj.status || obj.stage || "");
        const exitCode = typeof obj.exit_code === "number" ? obj.exit_code : undefined;

        // Check for error/failure payload
        const isFailed =
          eventType === "FAILED" ||
          eventType === "ERROR" ||
          status === "FAILED" ||
          status === "ERROR" ||
          (exitCode !== undefined && exitCode !== 0);

        if (isFailed) {
          closeStream();
          const errorMsg =
            String(obj.error || obj.message || obj.detail || "") ||
            (exitCode !== undefined
              ? `Process failed with exit code ${exitCode}`
              : "Background task failed.");
          if (options.onError) {
            options.onError(new Error(errorMsg));
          }
          return;
        }

        // Check for successful completion
        const isCompleted =
          eventType === "DONE" ||
          eventType === "COMPLETED" ||
          status === "DONE" ||
          status === "COMPLETED";

        if (isCompleted) {
          closeStream();
          if (options.onComplete) {
            options.onComplete();
          }
        }
      }
    } catch {
      // Raw string event
      options.onMessage(event.data as unknown as T);
    }
  };

  eventSource.onerror = () => {
    if (isClosed) return;
    // If the browser is in CONNECTING state (0), it is attempting auto-reconnect. Do not kill stream.
    if (eventSource.readyState === EventSource.CONNECTING) {
      return;
    }
    closeStream();
    if (options.onError) {
      options.onError(new Error("SSE stream terminated or process encountered an error."));
    }
  };

  return () => {
    closeStream();
  };
}
