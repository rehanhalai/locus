import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, X, Trash2, Cpu, FolderOpen, AlertCircle } from "lucide-react";
import type { ToolCallAction } from "@/types";
import { useCopilotStore } from "@/stores/useCopilotStore";
import { useCaseStore } from "@/stores/useCaseStore";
import { MessageScroller } from "./MessageScroller";
import { ChatBubble } from "./ChatBubble";
import { ChatInput } from "./ChatInput";

export const CopilotDrawer: React.FC = () => {
  const navigate = useNavigate();
  const isOpen = useCopilotStore((s) => s.isOpen);
  const closeCopilot = useCopilotStore((s) => s.closeCopilot);
  const toggleCopilot = useCopilotStore((s) => s.toggleCopilot);
  const messages = useCopilotStore((s) => s.messages);
  const isStreaming = useCopilotStore((s) => s.isStreaming);
  const status = useCopilotStore((s) => s.status);
  const sendMessage = useCopilotStore((s) => s.sendMessage);
  const stopStreaming = useCopilotStore((s) => s.stopStreaming);
  const clearMessages = useCopilotStore((s) => s.clearMessages);
  const executeAction = useCopilotStore((s) => s.executeAction);

  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);

  const handleExecuteAction = (action: ToolCallAction) => {
    executeAction(action);

    if (action.tool === "seek_player") {
      navigate("/investigate");
    } else if (action.tool === "search_detections") {
      navigate("/search");
    } else if (action.tool === "prepare_export") {
      navigate("/export");
    } else if (action.tool === "get_case_summary") {
      navigate("/cases");
    }
  };

  // Global Hotkey Listener: Ctrl+Space or Alt+C toggles drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Space or Alt+C or Cmd+Space
      if (
        (e.ctrlKey && e.code === "Space") ||
        (e.metaKey && e.code === "Space") ||
        (e.altKey && (e.key === "c" || e.key === "C"))
      ) {
        e.preventDefault();
        toggleCopilot();
      } else if (e.key === "Escape" && isOpen) {
        closeCopilot();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, toggleCopilot, closeCopilot]);

  if (!isOpen) return null;

  const handleSend = (text: string) => {
    if (!activeCaseId) {
      sendMessage(text, "unassigned_case");
      return;
    }
    sendMessage(text, activeCaseId);
  };

  const modelReady = status?.model_loaded ?? false;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs animate-in fade-in duration-200">
      {/* Backdrop overlay */}
      <div className="flex-1" onClick={closeCopilot} />

      {/* Drawer Container */}
      <div className="w-[450px] max-w-[95vw] h-full bg-zinc-950 border-l border-zinc-800 shadow-2xl flex flex-col select-none animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between bg-zinc-900/60 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-zinc-100">Forensic Copilot</h2>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  SLM
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] text-zinc-400 font-mono">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    modelReady ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
                  }`}
                />
                <span>
                  {modelReady ? "Qwen 2.5 1.5B (Local ONNX)" : "Deterministic Forensic Mode"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={clearMessages}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors cursor-pointer"
              title="Clear chat history"
            >
              <Trash2 className="w-4 h-4" />
            </button>
            <button
              onClick={closeCopilot}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors cursor-pointer"
              title="Close Copilot (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Active Case Context Bar */}
        <div className="px-4 py-2 border-b border-zinc-800/60 bg-zinc-900/30 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 truncate">
            <FolderOpen className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            {activeCaseId ? (
              <span className="truncate text-zinc-300">
                <span className="font-mono font-semibold text-indigo-300">
                  {activeCaseNumber || activeCaseId}
                </span>
                {activeCaseName && ` · ${activeCaseName}`}
              </span>
            ) : (
              <span className="text-amber-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>No active case (General query mode)</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 text-[10px] text-zinc-500 shrink-0 font-mono">
            <Cpu className="w-3 h-3 text-zinc-400" />
            <span>CPU INT4</span>
          </div>
        </div>

        {/* Messages Body */}
        <MessageScroller
          className="flex-1"
          autoScrollDependency={messages[messages.length - 1]?.content}
        >
          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} onExecuteAction={handleExecuteAction} />
          ))}
        </MessageScroller>

        {/* Input Footer */}
        <ChatInput
          onSend={handleSend}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          disabled={false}
          placeholder={
            activeCaseId
              ? `Ask about ${activeCaseNumber || "this case"}...`
              : "Ask Copilot a forensic query..."
          }
        />
      </div>
    </div>
  );
};
