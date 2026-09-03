export type EventLabel =
  | "person"
  | "car"
  | "truck"
  | "bus"
  | "motorcycle"
  | "bicycle"
  | "backpack"
  | "handbag"
  | "suitcase"
  | "cell_phone"
  | "laptop"
  | "knife"
  | "motion"
  | "motion_void"
  | string;

export interface TimelineEvent {
  id: string;
  clip_id?: string | null;
  evidence_id: string;
  camera_id: number;
  timestamp: string; // ISO UTC
  label: EventLabel;
  confidence: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  // Legacy / convenience fields
  bbox_ymin?: number;
  bbox_xmin?: number;
  bbox_ymax?: number;
  bbox_xmax?: number;
  frame_number?: number;
  is_motion?: boolean;
  thumbnail_url?: string;
  created_at?: string;
}

export interface EventFilter {
  camera_id?: number | null;
  labels?: string[];
  min_confidence?: number;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export interface EventSearchResponse {
  evidence_id: string;
  total_events: number;
  events: TimelineEvent[];
}

export interface AnalyticsProgressEvent {
  task_id: string;
  evidence_id: string;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  current_clip?: string | null;
  processed_clips: number;
  total_clips: number;
  processed_frames: number;
  total_frames: number;
  events_detected: number;
  progress_percent: number;
  error?: string | null;
}
