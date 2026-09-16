import React, { useState } from "react";
import { Bot, User, Copy, Check } from "lucide-react";
import type { ChatMessage, ToolCallAction } from "@/types";
import { ActionBadge } from "./ActionBadge";

interface ChatBubbleProps {
  message: ChatMessage;
  onExecuteAction?: (action: ToolCallAction) => void;
}

export const ChatBubble: React.FC<ChatBubbleProps> = ({ message, onExecuteAction }) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Strip JSON code blocks that were tool invocations so user gets clean narrative
  const cleanContent = message.content.replace(/```(?:json)?\s*\{[\s\S]*?\}\s*```/g, "").trim();

  return (
    <div
      className={`group flex gap-3 my-3 text-sm transition-opacity ${
        isUser ? "flex-row-reverse justify-start" : "flex-row justify-start"
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
          isUser
            ? "bg-zinc-700 text-zinc-200"
            : "bg-gradient-to-br from-indigo-500 to-cyan-600 text-white shadow-indigo-500/20 shadow-md"
        }`}
      >
        {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Content Container */}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs md:text-sm leading-relaxed ${
          isUser
            ? "bg-indigo-600 text-white rounded-tr-none shadow-sm"
            : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-tl-none shadow-sm"
        }`}
      >
        {/* Author header for assistant */}
        {!isUser && (
          <div className="flex items-center justify-between gap-2 mb-1 text-[11px] font-semibold text-indigo-400">
            <span className="flex items-center gap-1.5">
              <span>Forensic Copilot</span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            </span>
            <button
              onClick={handleCopy}
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-zinc-400 hover:text-zinc-200 rounded hover:bg-zinc-800 cursor-pointer"
              title="Copy message"
            >
              {copied ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        )}

        {/* Action Badges if any */}
        {message.actions && message.actions.length > 0 && (
          <div className="space-y-1 my-1.5">
            {message.actions.map((act, idx) => (
              <ActionBadge key={idx} action={act} onExecuteAction={onExecuteAction} />
            ))}
          </div>
        )}

        {/* Formatted Text Content */}
        {cleanContent && (
          <div className="whitespace-pre-wrap break-words font-sans">
            {cleanContent}
            {message.isStreaming && (
              <span className="inline-block w-1.5 h-3.5 ml-1 bg-indigo-400 animate-pulse align-middle" />
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`mt-1 text-[10px] text-right ${
            isUser ? "text-indigo-200/70" : "text-zinc-500"
          }`}
        >
          {message.timestamp}
        </div>
      </div>
    </div>
  );
};
