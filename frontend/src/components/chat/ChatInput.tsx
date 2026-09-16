import React, { useRef, useState } from "react";
import { Send, Square, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (content: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

const QUICK_PROMPTS = [
  { label: "📊 Case Summary", prompt: "Can you provide a forensic summary of this case?" },
  { label: "🔪 Find Knife", prompt: "Search detections for knife or weapon" },
  { label: "👤 Find Persons", prompt: "Search detections for persons in surveillance" },
  { label: "⏩ Jump to Cam 1", prompt: "Jump to camera 1 at 2026-03-29T14:22:00" },
  { label: "📦 Prepare Export", prompt: "Prepare evidence export for camera 1" },
];

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = "Ask Copilot about video evidence, objects, timestamps...",
}) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || disabled) return;

    onSend(text.trim());
    setText("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    // Auto-grow textarea
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  };

  const handleQuickPrompt = (prompt: string) => {
    if (disabled || isStreaming) return;
    onSend(prompt);
  };

  return (
    <div className="p-3 border-t border-zinc-800/80 bg-zinc-950/70 backdrop-blur-md">
      {/* Quick Prompt Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-1 scrollbar-none text-[11px]">
        <span className="text-zinc-500 flex items-center gap-1 shrink-0 px-1 font-medium">
          <Sparkles className="w-3 h-3 text-indigo-400" />
          <span>Quick:</span>
        </span>
        {QUICK_PROMPTS.map((qp, i) => (
          <button
            key={i}
            onClick={() => handleQuickPrompt(qp.prompt)}
            disabled={disabled || isStreaming}
            className="shrink-0 px-2.5 py-1 rounded-full border border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-all disabled:opacity-50 cursor-pointer"
          >
            {qp.label}
          </button>
        ))}
      </div>

      {/* Input Field & Buttons */}
      <form onSubmit={handleSubmit} className="relative flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          className="w-full resize-none py-2.5 pl-3.5 pr-12 rounded-xl bg-zinc-900/90 border border-zinc-700/60 text-xs md:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition-all max-h-32"
        />

        <div className="absolute right-2 bottom-2 flex items-center gap-1">
          {isStreaming ? (
            <button
              type="button"
              onClick={onStop}
              className="p-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white transition-colors cursor-pointer"
              title="Stop generation"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!text.trim() || disabled}
              className="p-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:hover:bg-indigo-600 transition-all cursor-pointer"
              title="Send message"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </form>
    </div>
  );
};
