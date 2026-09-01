import { api } from "./client";
import type { EventFilter, EventSearchResponse } from "../types/analytics";

export const analyticsApi = {
  // Flow 06: Local YOLOv8 + MOG2 Analytics processing
  startAnalytics: (payload: {
    evidence_id: string;
    clip_ids?: string[];
    confidence_threshold?: number;
    motion_gating?: boolean;
    target_classes?: string[];
  }) =>
    api.post<{
      task_id: string;
      evidence_id: string;
      status: string;
      message: string;
    }>("/analytics/process", payload),

  // Flow 07: Sub-second Event Search
  searchEvents: (evidenceId: string, filter?: EventFilter) => {
    const params: Record<string, string | number | undefined> = {};
    if (filter?.camera_id !== undefined && filter.camera_id !== null) {
      params.camera_id = filter.camera_id;
    }
    if (filter?.min_confidence !== undefined) {
      params.min_confidence = filter.min_confidence;
    }
    if (filter?.start_time) {
      params.start_time = filter.start_time;
    }
    if (filter?.end_time) {
      params.end_time = filter.end_time;
    }

    let url = `/analytics/events/${evidenceId}`;
    if (filter?.labels && filter.labels.length > 0) {
      const labelParams = filter.labels.map((l) => `labels=${encodeURIComponent(l)}`).join("&");
      url += `?${labelParams}`;
    }

    return api.get<EventSearchResponse>(url, params);
  },
};
