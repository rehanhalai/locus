import { X, Activity, CheckCircle2, AlertCircle, RefreshCw, Trash2 } from "lucide-react";
import { useCaseStore } from "../../stores/useCaseStore";
import { Progress } from "../ui/progress";
import { Button } from "../ui/button";

export function TaskDrawer() {
  const taskDrawerOpen = useCaseStore((s) => s.taskDrawerOpen);
  const setTaskDrawerOpen = useCaseStore((s) => s.setTaskDrawerOpen);
  const runningTasks = useCaseStore((s) => s.runningTasks);
  const removeTask = useCaseStore((s) => s.removeTask);

  if (!taskDrawerOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs animate-in fade-in duration-200">
      {/* Click outside backdrop to close */}
      <div className="flex-1" onClick={() => setTaskDrawerOpen(false)} />

      {/* Drawer Container */}
      <div className="w-96 h-full bg-card border-l border-border shadow-2xl flex flex-col p-5 select-none animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Activity className="size-4 text-primary animate-pulse" />
            <h2 className="font-heading text-sm font-semibold">Background Pipeline Tasks</h2>
          </div>
          <button
            onClick={() => setTaskDrawerOpen(false)}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Task List */}
        <div className="flex-1 overflow-y-auto py-4 space-y-3">
          {runningTasks.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-center text-muted-foreground space-y-2">
              <CheckCircle2 className="size-8 text-muted-foreground/40" />
              <p className="text-xs">No active pipeline jobs.</p>
              <p className="text-[11px] text-muted-foreground/60">
                Tasks like disk imaging, sector carving, and AI detection will stream progress here.
              </p>
            </div>
          ) : (
            runningTasks.map((task) => {
              const isDone = task.status === "COMPLETED" || task.status === "DONE";
              const isFailed = task.status === "FAILED";

              return (
                <div
                  key={task.task_id}
                  className="p-3 rounded-xl bg-secondary/50 border border-border space-y-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {isDone ? (
                        <CheckCircle2 className="size-4 text-emerald-400 shrink-0" />
                      ) : isFailed ? (
                        <AlertCircle className="size-4 text-destructive shrink-0" />
                      ) : (
                        <RefreshCw className="size-4 text-cyan-400 animate-spin shrink-0" />
                      )}
                      <span className="text-xs font-medium truncate">{task.title}</span>
                    </div>

                    <button
                      onClick={() => removeTask(task.task_id)}
                      className="text-muted-foreground/60 hover:text-destructive transition-colors"
                      title="Dismiss task"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[11px] font-mono text-muted-foreground">
                      <span>{task.status}</span>
                      <span>{task.progress_percent}%</span>
                    </div>
                    <Progress value={task.progress_percent} className="h-1.5" />
                  </div>

                  {/* Telemetry metadata */}
                  <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground/70">
                    {task.speed_mbps !== undefined && task.speed_mbps > 0 ? (
                      <span>Speed: {task.speed_mbps.toFixed(1)} MB/s</span>
                    ) : (
                      <span>ID: {task.task_id.slice(0, 8)}...</span>
                    )}
                    {task.message && (
                      <span className="truncate max-w-[140px]">{task.message}</span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-border flex justify-between items-center text-xs text-muted-foreground">
          <span>Press <kbd className="font-mono bg-muted px-1.5 py-0.5 rounded text-[10px] border border-border">T</kbd> to toggle</span>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => setTaskDrawerOpen(false)}
          >
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
