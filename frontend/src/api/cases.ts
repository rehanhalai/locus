import { api } from "./client";
import type {
  BlockDeviceInfo,
  Case,
  CaseCreatePayload,
  CaseStatus,
  CaseUpdatePayload,
  FsBrowseResponse,
} from "../types/case";

export const casesApi = {
  listCases: (status?: CaseStatus, search?: string) =>
    api.get<Case[]>("/cases/", { status, search }),

  getCase: (caseId: string) => api.get<Case>(`/cases/${caseId}`),

  createCase: (payload: CaseCreatePayload) => api.post<Case>("/cases/", payload),

  updateCase: (caseId: string, payload: CaseUpdatePayload) =>
    api.patch<Case>(`/cases/${caseId}`, payload),

  deleteCase: (caseId: string) => api.delete<void>(`/cases/${caseId}`),

  // Flow 01: Ingestion & Cloning
  ingestFile: (payload: { case_id: string; file_path: string; investigator?: string }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/acquisition/ingest-file",
      payload
    ),

  cloneDevice: (payload: {
    case_id: string;
    source_device: string;
    image_filename?: string;
    investigator?: string;
  }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/acquisition/clone",
      payload
    ),

  listDevices: () => api.get<BlockDeviceInfo[]>("/acquisition/devices"),

  browseFilesystem: (path?: string) =>
    api.get<FsBrowseResponse>("/acquisition/browse-fs", path ? { path } : undefined),

  getAcquisitionTasks: () =>
    api.get<
      Array<{
        task_id: string;
        case_id: string;
        source_device: string;
        output_path: string;
        status: string;
        latest_event?: unknown;
        created_at: string;
      }>
    >("/acquisition/tasks"),

  getAcquisitionTask: (taskId: string) =>
    api.get<{
      task_id: string;
      case_id: string;
      source_device: string;
      output_path: string;
      status: string;
      latest_event?: unknown;
      created_at: string;
    }>(`/acquisition/tasks/${taskId}`),

  // Flow 02: Identification
  identifyDevice: (payload: { evidence_id: string; deep_scan?: boolean; investigator?: string }) =>
    api.post<{ task_id: string; evidence_id: string; status: string; message: string }>(
      "/identify/device",
      payload
    ),

  getIdentificationResults: (evidenceId: string) =>
    api.get<{
      evidence_id: string;
      device_metadata: {
        total_sectors: number;
        sector_size_bytes: number;
        total_size_bytes: number;
        partition_table_type: string;
      };
      signatures: Array<{
        brand: string;
        filesystem: string;
        confidence: number;
        signature_name: string;
      }>;
      partitions: Array<{
        partition_index: number;
        start_sector: number;
        end_sector: number;
        total_sectors: number;
        filesystem_type: string;
      }>;
    }>(`/identify/results/${evidenceId}`),
};
