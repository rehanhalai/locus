import { useEffect, useRef, useState } from "react";
import { subscribeSSE } from "../api/sse";
import { useCaseStore } from "../stores/useCaseStore";
import type { BackgroundTask } from "../types";

export interface SSETaskProgressData {
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

export interface UseTaskSSEOptions<T = SSETaskProgressData> {
  taskId: string | null;
  taskType: BackgroundTask["type"];
  title: string;
  endpoint?: string;
  onMessage?: (data: T) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
}

export function useTaskSSE<T extends SSETaskProgressData = SSETaskProgressData>({
  taskId,
  taskType,
  title,
  endpoint,
  onMessage,
  onComplete,
  onError,
}: UseTaskSSEOptions<T>) {
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);
  const [progress, setProgress] = useState(0);
  const [speedMbps, setSpeedMbps] = useState(0);
  const [stage, setStage] = useState<string>("IDLE");
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState(false);

  const titleRef = useRef(title);
  const taskTypeRef = useRef(taskType);
  const onMessageRef = useRef(onMessage);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    titleRef.current = title;
    taskTypeRef.current = taskType;
    onMessageRef.current = onMessage;
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  });

  useEffect(() => {
    if (!taskId) return;

    // Register initial task in global store
    addOrUpdateTask({
      task_id: taskId,
      type: taskTypeRef.current,
      title: titleRef.current,
      status: "PROCESSING",
      progress_percent: 0,
      started_at: new Date().toISOString(),
    });

    const streamUrl = endpoint || `/acquisition/stream/${taskId}`;
    const unsubscribe = subscribeSSE<T>(streamUrl, {
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

        const currentStage = data.stage ?? data.status ?? "PROCESSING";
        const msg = data.message ?? "";

        const calculatedPct = Math.min(
          100,
          Math.max(0, pct >= 1 ? Math.round(pct * 10) / 10 : Math.round(pct * 100) / 100)
        );
        setProgress(calculatedPct);
        setSpeedMbps(speed);
        setStage(currentStage);
        if (msg) setMessage(msg);

        const isDone =
          currentStage === "DONE" || currentStage === "COMPLETED" || data.type === "COMPLETED";

        addOrUpdateTask({
          task_id: taskId,
          type: taskTypeRef.current,
          title: titleRef.current,
          status: isDone ? "COMPLETED" : "PROCESSING",
          progress_percent: isDone ? 100 : Math.round(calculatedPct),
          speed_mbps: speed,
          message: msg,
          started_at: new Date().toISOString(),
        });

        if (onMessageRef.current) {
          onMessageRef.current(data);
        }
      },
      onComplete: () => {
        setProgress(100);
        setIsCompleted(true);
        setStage("COMPLETED");
        addOrUpdateTask({
          task_id: taskId,
          type: taskTypeRef.current,
          title: titleRef.current,
          status: "COMPLETED",
          progress_percent: 100,
          started_at: new Date().toISOString(),
        });
        if (onCompleteRef.current) {
          onCompleteRef.current();
        }
      },
      onError: (err) => {
        setError(err.message);
        setStage("FAILED");
        addOrUpdateTask({
          task_id: taskId,
          type: taskTypeRef.current,
          title: titleRef.current,
          status: "FAILED",
          progress_percent: 0,
          error: err.message,
          started_at: new Date().toISOString(),
        });
        if (onErrorRef.current) {
          onErrorRef.current(err);
        }
      },
    });

    return () => {
      unsubscribe();
    };
  }, [taskId, endpoint, addOrUpdateTask]);

  return {
    progress: taskId ? progress : 0,
    speedMbps: taskId ? speedMbps : 0,
    stage: taskId ? stage : "IDLE",
    message: taskId ? message : "",
    error: taskId ? error : null,
    isCompleted: taskId ? isCompleted : false,
  };
}
