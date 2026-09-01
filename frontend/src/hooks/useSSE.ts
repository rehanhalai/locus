import { useEffect, useRef } from "react";
import { subscribeSSE } from "../api/sse";
import { useCaseStore } from "../stores/useCaseStore";
import type { BackgroundTask } from "../types";

export function useTaskSSE(
  taskId: string | null,
  taskType: BackgroundTask["type"],
  title: string,
  onComplete?: () => void
) {
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    if (!taskId) return;

    // Register initial task
    addOrUpdateTask({
      task_id: taskId,
      type: taskType,
      title,
      status: "PROCESSING",
      progress_percent: 0,
      started_at: new Date().toISOString(),
    });

    const unsubscribe = subscribeSSE(
      taskId.startsWith("/api") ? taskId : `/acquisition/stream/${taskId}`,
      {
        onMessage: (data: any) => {
          const percent = data.progress_percent || data.percentage || data.progress || 0;
          const speed = data.speed_mbps || data.speed_mb_s || data.rate_mb_s || 0;
          const status = data.status || data.stage || "PROCESSING";
          const message = data.message || data.status_message || "";

          addOrUpdateTask({
            task_id: taskId,
            type: taskType,
            title,
            status: status === "DONE" || status === "COMPLETED" ? "COMPLETED" : "PROCESSING",
            progress_percent: Math.min(100, Math.max(0, Math.round(percent))),
            speed_mbps: speed,
            message,
            started_at: new Date().toISOString(),
          });
        },
        onComplete: () => {
          addOrUpdateTask({
            task_id: taskId,
            type: taskType,
            title,
            status: "COMPLETED",
            progress_percent: 100,
            started_at: new Date().toISOString(),
          });
          if (onCompleteRef.current) {
            onCompleteRef.current();
          }
        },
        onError: (err) => {
          addOrUpdateTask({
            task_id: taskId,
            type: taskType,
            title,
            status: "FAILED",
            progress_percent: 0,
            error: err.message,
            started_at: new Date().toISOString(),
          });
        },
      }
    );

    return () => {
      unsubscribe();
    };
  }, [taskId, taskType, title, addOrUpdateTask]);
}
