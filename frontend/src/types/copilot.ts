export type MessageRole = "user" | "assistant" | "system";

export interface ToolCallAction {
  tool: "get_case_summary" | "search_detections" | "seek_player" | "prepare_export" | string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  actions?: ToolCallAction[];
  isStreaming?: boolean;
}

export interface CopilotStatus {
  status: "online" | "fallback_mode" | "offline";
  model_loaded: boolean;
  model_name: string;
  execution_provider: string;
  tools_available: string[];
}

export interface ChatRequest {
  case_id: string;
  messages: Array<{
    role: MessageRole;
    content: string;
  }>;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}
