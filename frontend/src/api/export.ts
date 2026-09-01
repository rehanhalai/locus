import { api } from "./client";
import type { EvidenceExport, VerifyResult, SyncSidecarManifest } from "../types/export";

export const exportApi = {
  // Flow 08: Slicing & Verification
  exportSlice: (payload: {
    evidence_id: string;
    camera_id: number;
    start_time: string;
    end_time: string;
    investigator?: string;
    reason?: string;
  }) =>
    api.post<EvidenceExport>("/export/slice", payload),

  getExportDetails: (exportId: string) =>
    api.get<EvidenceExport>(`/export/${exportId}`),

  verifyIntegrity: (payload: { file_sha256?: string; manifest_json?: string }) =>
    api.post<VerifyResult>("/export/verify", payload),

  recoverManifestByHash: (fileSha256: string) =>
    api.post<SyncSidecarManifest>("/export/recover-by-hash", { file_sha256: fileSha256 }),

  // Flow 09: PDF Report Generation & Summary
  generateCaseReport: (caseId: string, investigator?: string) =>
    api.post<{
      report_id: string;
      case_id: string;
      case_number: string;
      generated_at: string;
      file_size_bytes: number;
      download_url: string;
    }>(`/reports/generate/${caseId}?investigator=${encodeURIComponent(investigator || "Forensic Officer")}`),

  getCaseSummary: (caseId: string) =>
    api.get<{
      case_id: string;
      case_number: string;
      case_name: string;
      investigator: string;
      total_evidence_files: number;
      total_carved_clips: number;
      total_timeline_events: number;
      total_audit_logs: number;
    }>(`/reports/summary/${caseId}`),

  getPdfDownloadUrl: (caseId: string, investigator?: string) => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
    return `${baseUrl}/reports/pdf/${caseId}?investigator=${encodeURIComponent(investigator || "Forensic Officer")}`;
  },
};
