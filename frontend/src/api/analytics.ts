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
    const params = new URLSearchParams();

    if (filter?.camera_id !== undefined && filter.camera_id !== null) {
      params.append("camera_id", String(filter.camera_id));
    }
    if (filter?.min_confidence !== undefined) {
      params.append("min_confidence", String(filter.min_confidence));
    }
    if (filter?.start_time) {
      params.append("start_time", filter.start_time);
    }
    if (filter?.end_time) {
      params.append("end_time", filter.end_time);
    }
    if (filter?.limit !== undefined) {
      params.append("limit", String(filter.limit));
    }
    if (filter?.offset !== undefined) {
      params.append("offset", String(filter.offset));
    }
    if (filter?.labels && filter.labels.length > 0) {
      filter.labels.forEach((l) => params.append("labels", l));
    }

    const qs = params.toString();
    const url = `/analytics/events/${evidenceId}${qs ? `?${qs}` : ""}`;
    return api.get<EventSearchResponse>(url);
  },
};
