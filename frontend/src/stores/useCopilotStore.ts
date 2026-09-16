import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ChatMessage, CopilotStatus, ToolCallAction } from "@/types";
import { fetchCopilotStatus, streamCopilotChat } from "@/api/copilot";
import { useCaseStore } from "./useCaseStore";

interface CopilotState {
  isOpen: boolean;
  messages: ChatMessage[];
  isStreaming: boolean;
  status: CopilotStatus | null;
  abortController: AbortController | null;

  // Drawer actions
  openCopilot: () => void;
  closeCopilot: () => void;
  toggleCopilot: () => void;

  // Chat actions
  fetchStatus: () => Promise<void>;
  sendMessage: (content: string, caseId: string) => Promise<void>;
  stopStreaming: () => void;
  clearMessages: () => void;
  executeAction: (action: ToolCallAction) => void;
}

const INITIAL_GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  content:
    "Hello Investigator. I am LOCUS Forensic Copilot, your offline local AI assistant running on Qwen 2.5 1.5B. I can analyze surveillance video evidence, search object detections, synchronize video playback, and prepare court-admissible evidence exports. How can I assist with this case?",
  timestamp: "Ready",
};

export const useCopilotStore = create<CopilotState>()(
  persist(
    (set, get) => ({
      isOpen: false,
      messages: [INITIAL_GREETING],
      isStreaming: false,
      status: null,
      abortController: null,

      openCopilot: () => {
        set({ isOpen: true });
        if (!get().status) {
          get().fetchStatus();
        }
      },

      closeCopilot: () => set({ isOpen: false }),

      toggleCopilot: () => {
        const next = !get().isOpen;
        set({ isOpen: next });
        if (next && !get().status) {
          get().fetchStatus();
        }
      },

      fetchStatus: async () => {
        try {
          const status = await fetchCopilotStatus();
          set({ status });
        } catch {
          set({
            status: {
              status: "offline",
              model_loaded: false,
              model_name: "Offline",
              execution_provider: "CPU",
              tools_available: [],
            },
          });
        }
      },

      stopStreaming: () => {
        const { abortController } = get();
        if (abortController) {
          abortController.abort();
        }
        set({ isStreaming: false, abortController: null });
      },

      clearMessages: () => set({ messages: [INITIAL_GREETING] }),

      sendMessage: async (content: string, caseId: string) => {
        if (!content.trim() || !caseId) return;

        // Abort any ongoing stream
        get().stopStreaming();

        const userMsgId = `user_${Date.now()}`;
        const assistantMsgId = `assistant_${Date.now()}`;
        const nowStr = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        const userMessage: ChatMessage = {
          id: userMsgId,
          role: "user",
          content,
          timestamp: nowStr,
        };

        const assistantMessage: ChatMessage = {
          id: assistantMsgId,
          role: "assistant",
          content: "",
          timestamp: nowStr,
          actions: [],
          isStreaming: true,
        };

        const currentMessages = get().messages;
        set({
          messages: [...currentMessages, userMessage, assistantMessage],
          isStreaming: true,
        });

        const abortController = new AbortController();
        set({ abortController });

        // Map messages for API
        const historyForApi = [...currentMessages, userMessage]
          .filter((m) => m.id !== "greeting")
          .map((m) => ({
            role: m.role,
            content: m.content,
          }));

        let accumulatedContent = "";
        const accumulatedActions: ToolCallAction[] = [];

        await streamCopilotChat(
          {
            case_id: caseId,
            messages: historyForApi,
            stream: true,
          },
          {
            onToken: (chunk: string) => {
              accumulatedContent += chunk;
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, content: accumulatedContent }
                    : m
                ),
              }));
            },
            onAction: (action: ToolCallAction) => {
              accumulatedActions.push(action);
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, actions: [...accumulatedActions] }
                    : m
                ),
              }));

              // Auto-dispatch seek_player if investigator requested it
              if (action.tool === "seek_player") {
                get().executeAction(action);
              }
            },
            onDone: () => {
              set((state) => ({
                isStreaming: false,
                abortController: null,
                messages: state.messages.map((m) =>
                  m.id === assistantMsgId ? { ...m, isStreaming: false } : m
                ),
              }));
            },
            onError: (err: Error) => {
              set((state) => ({
                isStreaming: false,
                abortController: null,
                messages: state.messages.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content:
                          m.content ||
                          `Copilot request error: ${err.message}. Check backend connection.`,
                        isStreaming: false,
                      }
                    : m
                ),
              }));
            },
          },
          abortController.signal
        );
      },

      executeAction: (action: ToolCallAction) => {
        const caseStore = useCaseStore.getState();

        if (action.tool === "seek_player") {
          const cam = action.arguments.camera_id;
          const ts = action.arguments.timestamp;
          if (cam !== undefined) {
            caseStore.setFocusedCameraId(cam);
          }
          if (ts) {
            caseStore.setMasterPlayheadTime(ts);
          }
          caseStore.setActiveRoom("investigate");
        } else if (action.tool === "search_detections") {
          caseStore.setActiveRoom("search");
        } else if (action.tool === "prepare_export") {
          caseStore.setActiveRoom("export");
        }
      },
    }),
    {
      name: "locus-copilot-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        messages: state.messages.slice(-30), // persist up to last 30 messages
      }),
    }
  )
);
