import React, { useEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";

interface MessageScrollerProps {
  children: React.ReactNode;
  className?: string;
  autoScrollDependency?: any;
}

export const MessageScroller: React.FC<MessageScrollerProps> = ({
  children,
  className = "",
  autoScrollDependency,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  const checkIfAtBottom = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    // 40px threshold for feeling at the bottom
    const atBottom = scrollHeight - scrollTop - clientHeight <= 40;
    setIsAtBottom(atBottom);
  };

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior,
    });
  };

  // Auto-scroll when dependencies update (e.g. streaming tokens or new messages)
  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom("auto");
    }
  }, [autoScrollDependency, isAtBottom]);

  return (
    <div className="relative flex-1 overflow-hidden h-full flex flex-col">
      <div
        ref={scrollRef}
        onScroll={checkIfAtBottom}
        className={`flex-1 overflow-y-auto px-4 py-2 space-y-2 scrollbar-thin scrollbar-thumb-zinc-800 ${className}`}
      >
        {children}
      </div>

      {/* Floating Scroll to Bottom button */}
      {!isAtBottom && (
        <button
          onClick={() => {
            scrollToBottom("smooth");
            setIsAtBottom(true);
          }}
          className="absolute bottom-3 right-6 z-10 p-2 rounded-full bg-zinc-800/90 border border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-700 transition-all shadow-lg flex items-center justify-center cursor-pointer animate-fade-in"
          title="Scroll to bottom"
        >
          <ArrowDown className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
