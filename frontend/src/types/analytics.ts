export type EventLabel =
  "person" | "car" | "truck" | "bus" | "motorcycle" | "bicycle" | "motion_void";

export interface TimelineEvent {
  id: string;
  clip_id: string;
  evidence_id: string;
  camera_id: number;
  timestamp: string; // ISO UTC
  label: EventLabel;
  confidence: number;
  bbox_ymin?: number;
  bbox_xmin?: number;
  bbox_ymax?: number;
  bbox_xmax?: number;
  frame_number?: number;
  thumbnail_url?: string;
}

export interface EventFilter {
  camera_id?: number | null;
  labels?: EventLabel[];
  min_confidence: number;
  start_time?: string;
  end_time?: string;
}

export interface EventSearchResponse {
  evidence_id: string;
  total_events: number;
  events: TimelineEvent[];
}
