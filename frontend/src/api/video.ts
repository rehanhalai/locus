import { api } from "./client";
import type { CarvedClip, Calibration, GridSyncFrameResponse } from "../types/video";

export const videoApi = {
  // Flow 03: Header parsing
  parseHeaders: (payload: {
    evidence_id: string;
    partition_index?: number;
    investigator?: string;
  }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/headers/parse",
      payload
    ),

  getMasterMapResults: (evidenceId: string) =>
    api.get<{
      evidence_id: string;
      total_chunks: number;
      total_frames: number;
      camera_summaries: Record<number, { frame_count: number; keyframe_count: number }>;
      chunks: Array<{
        camera_id: number;
        start_sector: number;
        end_sector: number;
        start_time: string;
        end_time: string;
        frame_count: number;
      }>;
    }>(`/headers/results/${evidenceId}`),

  // Flow 04: Carver
  carveSingleClip: (payload: {
    evidence_id: string;
    camera_id: number;
    start_sector: number;
    end_sector: number;
    start_time?: string;
    end_time?: string;
    investigator?: string;
  }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/carver/clip",
      payload
    ),

  carveAllClips: (payload: { evidence_id: string; investigator?: string }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/carver/all",
      payload
    ),

  getCarvedClips: (evidenceId: string) =>
    api.get<{
      evidence_id: string;
      status: string;
      total_clips: number;
      total_size_bytes: number;
      clips: CarvedClip[];
    }>(`/carver/results/${evidenceId}`),

  getVideoStreamUrl: (clipId: string) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
    return `${baseUrl}/carver/stream/${clipId}`;
  },

  // Flow 05: Master timeline sync & clock calibrations
  getMasterTimeline: (evidenceId: string) =>
    api.get<{
      evidence_id: string;
      min_master_time: string;
      max_master_time: string;
      total_duration_seconds: number;
      tracks: Array<{
        camera_id: number;
        channel_name: string;
        calibration_offset_seconds: number;
        clips: Array<{
          clip_id: string;
          start_time: string;
          end_time: string;
          duration_seconds: number;
          stream_url: string;
        }>;
      }>;
    }>(`/timeline/${evidenceId}`),

  setCalibration: (payload: {
    evidence_id: string;
    camera_id: number;
    offset_seconds: number;
    reason?: string;
    investigator?: string;
  }) => api.post<Calibration>("/timeline/calibrate", payload),

  getCalibrations: (evidenceId: string) =>
    api.get<Calibration[]>(`/timeline/calibrations/${evidenceId}`),

  resetCalibration: (evidenceId: string, cameraId: number, investigator?: string) =>
    api.delete<{ status: string; message: string }>(
      `/timeline/calibrate/${evidenceId}/${cameraId}?investigator=${encodeURIComponent(
        investigator || "Forensic Officer"
      )}`
    ),

  resolveGridSyncFrame: (evidenceId: string, timestamp: string) =>
    api.get<GridSyncFrameResponse>(`/timeline/sync-frame/${evidenceId}`, {
      timestamp,
    }),
};
