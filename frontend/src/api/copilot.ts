import type { ChatRequest, CopilotStatus, ToolCallAction } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export async function fetchCopilotStatus(): Promise<CopilotStatus> {
  const res = await fetch(`${BASE_URL}/copilot/status`);
  if (!res.ok) {
    throw new Error(`Failed to fetch copilot status: ${res.statusText}`);
  }
  return res.json();
}

export interface StreamChatCallbacks {
  onToken: (chunk: string) => void;
  onAction?: (action: ToolCallAction) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}

/**
 * Streams chat tokens and tool execution results from the local Copilot via SSE POST.
 */
export async function streamCopilotChat(
  request: ChatRequest,
  callbacks: StreamChatCallbacks,
  signal?: AbortSignal
): Promise<void> {
  try {
    const res = await fetch(`${BASE_URL}/copilot/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ...request, stream: true }),
      signal,
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Copilot chat failed (${res.status}): ${errorText}`);
    }

    if (!res.body) {
      throw new Error("ReadableStream not supported by response body.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);

          if (event.type === "token" && typeof event.content === "string") {
            callbacks.onToken(event.content);
          } else if (event.type === "tool_call" || event.type === "tool_result") {
            if (callbacks.onAction) {
              callbacks.onAction({
                tool: event.tool,
                arguments: event.arguments || {},
                result: event.result,
              });
            }
          } else if (event.type === "done") {
            callbacks.onDone?.();
          } else if (event.type === "error") {
            callbacks.onError?.(new Error(event.error || "Unknown stream error"));
          }
        } catch {
          // If chunk is partial or invalid JSON, ignore and continue
        }
      }
    }

    callbacks.onDone?.();
  } catch (err: any) {
    if (err.name === "AbortError") {
      callbacks.onDone?.();
      return;
    }
    callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
  }
}

export async function sendCopilotChatSync(request: ChatRequest) {
  const res = await fetch(`${BASE_URL}/copilot/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ...request, stream: false }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Copilot chat failed (${res.status}): ${errorText}`);
  }

  return res.json();
}
