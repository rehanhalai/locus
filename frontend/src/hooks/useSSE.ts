import { useEffect, useRef, useState } from "react";
import { subscribeSSE } from "../api/sse";
import { useCaseStore } from "../stores/useCaseStore";
import type { BackgroundTask } from "../types";

export interface SSETaskProgressData {
  stage?: string;
  status?: string;
  type?: string;
  percentage?: number;
  progress_percent?: number;
  progress?: number;
  speed_mbps?: number;
  speed_mb_s?: number;
  rate_mb_s?: number;
  bytes_processed?: number;
  total_bytes?: number;
  sha256?: string;
  md5?: string;
  evidence_id?: string;
  device_brand?: string;
  message?: string;
  status_message?: string;
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

  const onMessageRef = useRef(onMessage);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
  });

  useEffect(() => {
    if (!taskId) return;

    // Register initial task in global store
    addOrUpdateTask({
      task_id: taskId,
      type: taskType,
      title,
      status: "PROCESSING",
      progress_percent: 0,
      started_at: new Date().toISOString(),
    });

    const streamUrl = endpoint || `/acquisition/stream/${taskId}`;
    const unsubscribe = subscribeSSE<T>(streamUrl, {
      onMessage: (data) => {
        const pct = data.percentage ?? data.progress_percent ?? data.progress ?? 0;
        const speed = data.speed_mbps ?? data.speed_mb_s ?? data.rate_mb_s ?? 0;
        const currentStage = data.stage ?? data.status ?? "PROCESSING";
        const msg = data.message ?? data.status_message ?? "";

        const roundedPct = Math.min(100, Math.max(0, Math.round(pct)));
        setProgress(roundedPct);
        setSpeedMbps(speed);
        setStage(currentStage);
        if (msg) setMessage(msg);

        const isDone =
          currentStage === "DONE" || currentStage === "COMPLETED" || data.type === "COMPLETED";

        addOrUpdateTask({
          task_id: taskId,
          type: taskType,
          title,
          status: isDone ? "COMPLETED" : "PROCESSING",
          progress_percent: isDone ? 100 : roundedPct,
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
        setError(err.message);
        setStage("FAILED");
        addOrUpdateTask({
          task_id: taskId,
          type: taskType,
          title,
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
  }, [taskId, taskType, title, endpoint, addOrUpdateTask]);

  return {
    progress: taskId ? progress : 0,
    speedMbps: taskId ? speedMbps : 0,
    stage: taskId ? stage : "IDLE",
    message: taskId ? message : "",
    error: taskId ? error : null,
    isCompleted: taskId ? isCompleted : false,
  };
}
