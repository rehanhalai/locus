export * from "./case";
export * from "./video";
export * from "./analytics";
export * from "./export";

export type RoomId = "cases" | "investigate" | "search" | "export" | "audit";

export interface BackgroundTask {
  task_id: string;
  type: "ingestion" | "identification" | "header_parsing" | "carving" | "analytics";
  title: string;
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "DONE";
  progress_percent: number;
  speed_mbps?: number;
  message?: string;
  started_at: string;
  error?: string;
}
