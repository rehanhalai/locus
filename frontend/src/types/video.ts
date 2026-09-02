export interface CarvedClip {
  id: string;
  evidence_id: string;
  camera_id: number;
  start_sector: number;
  end_sector: number;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  frame_count: number;
  file_path: string;
  file_size_bytes: number;
  codec?: string;
  resolution?: string;
  sha256_hash?: string;
  stream_url?: string;
  created_at?: string;
}

export interface CameraChannel {
  camera_id: number;
  channel_name: string;
  clip_count: number;
  min_time?: string;
  max_time?: string;
  is_active: boolean;
}

export interface CameraTileSync {
  clip_id: string | null;
  seek_offset_seconds: number;
  stream_url: string | null;
  is_active: boolean;
  status: "ACTIVE" | "NO_SIGNAL" | "BUFFERING" | "IDLE";
}

export interface GridSyncFrameResponse {
  evidence_id: string;
  master_timestamp: string;
  active_cameras_count: number;
  tiles: Record<number, CameraTileSync>;
}

export interface Calibration {
  id: string;
  evidence_id: string;
  camera_id: number;
  offset_seconds: number;
  reason?: string;
  investigator: string;
  applied_at: string;
}
