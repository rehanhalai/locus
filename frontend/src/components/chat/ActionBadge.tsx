import React from "react";
import {
  FileText,
  Crosshair,
  Compass,
  DownloadCloud,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import type { ToolCallAction } from "@/types";

interface ActionBadgeProps {
  action: ToolCallAction;
  onExecuteAction?: (action: ToolCallAction) => void;
}

export const ActionBadge: React.FC<ActionBadgeProps> = ({ action, onExecuteAction }) => {
  const { tool, arguments: args, result } = action;

  if (tool === "seek_player") {
    const cam = typeof args.camera_id === "number" ? args.camera_id : Number(args.camera_id) || 1;
    const ts = typeof args.timestamp === "string" ? args.timestamp : String(args.timestamp || "");
    const shortTs = ts.includes("T") ? ts.split("T")[1]?.slice(0, 8) : ts;

    return (
      <div className="flex items-center justify-between gap-3 p-2.5 my-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/20 text-xs">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-cyan-500/10 text-cyan-400">
            <Compass className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="font-medium text-cyan-200">Seek Video &bull; Camera {cam}</div>
            <div className="text-[11px] text-zinc-400 font-mono">Timestamp: {shortTs || ts}</div>
          </div>
        </div>
        <button
          onClick={() => onExecuteAction?.(action)}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-[11px] transition-colors shadow-sm cursor-pointer"
        >
          <span>Jump</span>
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    );
  }

  if (tool === "search_detections") {
    const label = typeof args.label === "string" ? args.label : "objects";
    const totalFound = typeof result?.total_found === "number" ? result.total_found : 0;

    return (
      <div className="flex items-center justify-between gap-3 p-2.5 my-1.5 rounded-lg border border-emerald-500/30 bg-emerald-950/20 text-xs">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
            <Crosshair className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="font-medium text-emerald-200 capitalize">Object Search: {label}</div>
            <div className="text-[11px] text-zinc-400">
              {totalFound > 0 ? (
                <span className="text-emerald-300 font-medium">
                  {totalFound} occurrence{totalFound === 1 ? "" : "s"} indexed
                </span>
              ) : (
                "0 occurrences found"
              )}
            </div>
          </div>
        </div>
        {totalFound > 0 && (
          <button
            onClick={() => onExecuteAction?.(action)}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-[11px] transition-colors shadow-sm cursor-pointer"
          >
            <span>View</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }

  if (tool === "prepare_export") {
    const cam = typeof args.camera_id === "number" ? args.camera_id : Number(args.camera_id) || 1;

    return (
      <div className="flex items-center justify-between gap-3 p-2.5 my-1.5 rounded-lg border border-purple-500/30 bg-purple-950/20 text-xs">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400">
            <DownloadCloud className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="font-medium text-purple-200">Court Evidence Export Slice</div>
            <div className="text-[11px] text-zinc-400">
              Camera {cam} &bull; Forensic Signature Ready
            </div>
          </div>
        </div>
        <button
          onClick={() => onExecuteAction?.(action)}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-purple-600 hover:bg-purple-500 text-white font-medium text-[11px] transition-colors shadow-sm cursor-pointer"
        >
          <span>Export</span>
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    );
  }

  if (tool === "get_case_summary") {
    const caseNum = typeof result?.case_number === "string" ? result.case_number : undefined;
    const evCount = typeof result?.evidence_count === "number" ? result.evidence_count : 0;
    const clipCount = typeof result?.total_clips === "number" ? result.total_clips : 0;

    return (
      <div className="flex items-center justify-between gap-3 p-2.5 my-1.5 rounded-lg border border-amber-500/30 bg-amber-950/20 text-xs">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-400">
            <FileText className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="font-medium text-amber-200">Case Forensic Audit Summary</div>
            <div className="text-[11px] text-zinc-400">
              {caseNum ? `Case #${caseNum}` : "Overview"} &bull; {evCount} evidence &bull;{" "}
              {clipCount} clips
            </div>
          </div>
        </div>
        <button
          onClick={() => onExecuteAction?.(action)}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-medium text-[11px] transition-colors shadow-sm cursor-pointer"
        >
          <span>View</span>
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 p-2 my-1 rounded border border-zinc-700 bg-zinc-800/40 text-xs text-zinc-300">
      <CheckCircle2 className="w-3.5 h-3.5 text-zinc-400" />
      <span>Forensic Tool: {tool}</span>
    </div>
  );
};
