export interface EvidenceExport {
  id: string;
  case_id: string;
  evidence_id: string;
  camera_id: number;
  exported_filename: string;
  exported_file_path: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  sha256_hash: string;
  hmac_signature?: string;
  manifest_json?: string;
  created_at: string;
  investigator: string;
  reason?: string;
  download_video_url?: string;
  download_manifest_url?: string;
  download_bundle_url?: string;
}

export interface VerifyResult {
  is_authentic: boolean;
  file_sha256: string;
  stored_sha256?: string;
  match_source?: string;
  message: string;
  timestamp: string;
}

export interface SyncSidecarManifest {
  version: string;
  case_id: string;
  evidence_id: string;
  camera_id: number;
  exported_filename: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  file_sha256: string;
  original_evidence_sha256: string;
  calibrated_offset_seconds: number;
  exported_at: string;
  investigator: string;
  export_reason?: string;
  signature_hmac: string;
}
