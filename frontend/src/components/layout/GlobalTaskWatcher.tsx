import { useEffect, useState, useMemo } from "react";
import { RefreshCw, ChevronUp, ChevronDown, X } from "lucide-react";
import { useCaseStore } from "../../stores/useCaseStore";
import { subscribeSSE } from "../../api/sse";
import type { BackgroundTask } from "../../types";
import { Progress } from "../ui/progress";
import { Button } from "../ui/button";

interface SSEMessageData {
  type?: string;
  stage?: string;
  status?: string;
  percent?: number;
  progress_percent?: number;
  percentage?: number;
  speed?: string | number;
  speed_mbps?: number;
  speed_mb_s?: number;
  processed_bytes?: number;
  total_bytes?: number;
  sha256?: string;
  md5?: string;
  evidence_id?: string;
  device_brand?: string;
  message?: string;
  error?: string;
}

export function GlobalTaskWatcher() {
  const runningTasks = useCaseStore((s) => s.runningTasks);
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);
  const removeTask = useCaseStore((s) => s.removeTask);
  const toggleTaskDrawer = useCaseStore((s) => s.toggleTaskDrawer);
  const setActiveEvidenceId = useCaseStore((s) => s.setActiveEvidenceId);

  const [isMinimized, setIsMinimized] = useState(false);

  // Active jobs that need live SSE subscription
  const activeTasks = useMemo<BackgroundTask[]>(
    () =>
      runningTasks.filter(
        (t: BackgroundTask) => t.status === "PROCESSING" || t.status === "PENDING"
      ),
    [runningTasks]
  );
  const activeTaskIds = useMemo(
    () => activeTasks.map((t: BackgroundTask) => t.task_id).join(","),
    [activeTasks]
  );

  // Subscribe to SSE for every active task (reconnects on page refresh!)
  useEffect(() => {
    if (activeTasks.length === 0) return;

    const unsubscribers = activeTasks.map((task: BackgroundTask) => {
      let streamUrl = `/acquisition/stream/${task.task_id}`;
      if (task.type === "carving" || task.task_id.startsWith("carve_")) {
        streamUrl = `/carver/progress/${task.task_id}`;
      } else if (task.type === "identification" || task.task_id.startsWith("ident_")) {
        streamUrl = `/identification/stream/${task.task_id}`;
      }

      return subscribeSSE<SSEMessageData>(streamUrl, {
        onMessage: (data) => {
          let pct = data.percent ?? data.percentage ?? data.progress_percent;
          if (pct === undefined || pct === null) {
            const proc = data.processed_bytes;
            const tot = data.total_bytes;
            if (proc !== undefined && tot && tot > 0) {
              pct = (proc / tot) * 100;
            } else {
              pct = 0;
            }
          }

          const speed =
            typeof data.speed === "number"
              ? data.speed
              : typeof data.speed === "string"
                ? parseFloat(data.speed) || 0
                : (data.speed_mbps ?? data.speed_mb_s ?? 0);

          const isCompleted =
            data.type === "COMPLETED" ||
            data.status === "COMPLETED" ||
            data.stage === "COMPLETED" ||
            pct >= 100;

          if (data.evidence_id) {
            setActiveEvidenceId(data.evidence_id);
          }

          addOrUpdateTask({
            task_id: task.task_id,
            type: task.type,
            title: task.title,
            status: isCompleted ? "COMPLETED" : "PROCESSING",
            progress_percent: Math.min(100, Math.max(0, Math.round(pct))),
            speed_mbps: speed,
            message: data.message || data.stage || "Processing evidence stream...",
            started_at: task.started_at,
          });
        },
        onComplete: () => {
          addOrUpdateTask({
            task_id: task.task_id,
            type: task.type,
            title: task.title,
            status: "COMPLETED",
            progress_percent: 100,
            speed_mbps: 0,
            message: "Completed",
            started_at: task.started_at,
          });
        },
        onError: () => {
          // Clean closure on completion
        },
      });
    });

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [activeTaskIds, activeTasks, addOrUpdateTask, setActiveEvidenceId]);

  if (activeTasks.length === 0) return null;

  const primaryTask = activeTasks[0];

  return (
    <aside
      aria-label="Active forensic background task"
      className="fixed bottom-4 right-4 z-40 max-w-sm w-full bg-card/95 backdrop-blur-md border border-primary/30 rounded-2xl shadow-2xl overflow-hidden transition-all animate-in slide-in-from-bottom-5 duration-300"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-primary/10 border-b border-primary/20">
        <div className="flex items-center gap-2 min-w-0">
          <RefreshCw className="size-3.5 text-primary animate-spin shrink-0" />
          <span className="font-heading text-xs font-semibold text-foreground truncate">
            {primaryTask.title || "Forensic Ingestion in Progress"}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => setIsMinimized(!isMinimized)}
            className="text-muted-foreground hover:text-foreground h-6 w-6"
            title={isMinimized ? "Expand" : "Minimize"}
          >
            {isMinimized ? (
              <ChevronUp className="size-3.5" />
            ) : (
              <ChevronDown className="size-3.5" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => removeTask(primaryTask.task_id)}
            className="text-muted-foreground hover:text-destructive h-6 w-6"
            title="Dismiss from screen"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* Body */}
      {!isMinimized && (
        <div className="p-3.5 space-y-3">
          {/* Progress Bar & Percentage */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-muted-foreground font-medium flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-cyan-400 animate-ping" />
                {primaryTask.message || "Dual Hashing & Acquisition"}
              </span>
              <span className="font-bold text-primary">{primaryTask.progress_percent}%</span>
            </div>
            <Progress value={primaryTask.progress_percent} className="h-2" />
          </div>

          {/* Speed & Actions */}
          <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground pt-1">
            <span>
              {primaryTask.speed_mbps && primaryTask.speed_mbps > 0
                ? `⚡ ${primaryTask.speed_mbps.toFixed(1)} MB/s`
                : "Calculating throughput..."}
            </span>

            <Button
              variant="outline"
              size="xs"
              onClick={toggleTaskDrawer}
              className="text-[10px] h-6 px-2 font-sans border-border/80 hover:border-primary/50"
            >
              All Tasks ({activeTasks.length})
            </Button>
          </div>
        </div>
      )}
    </aside>
  );
}
