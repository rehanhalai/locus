export type CaseStatus = "ACTIVE" | "ARCHIVED" | "CLOSED";
export type IntegrityStatus = "UNVERIFIED" | "VERIFIED" | "TAMPERED" | "CORRUPTED";

export interface EvidenceFile {
  id: string;
  case_id: string;
  filename: string;
  source_path: string;
  raw_image_path?: string;
  file_size_bytes: number;
  sha256_hash: string;
  md5_hash: string;
  device_brand?: string;
  filesystem_type?: string;
  is_carved: boolean;
  is_indexed: boolean;
  created_at: string;
}

export interface AuditLog {
  id: string;
  case_id: string;
  timestamp: string;
  action: string;
  investigator: string;
  ip_address?: string;
  details?: Record<string, unknown> | string;
}

export interface Case {
  id: string;
  case_number: string;
  case_name: string;
  investigator: string;
  description?: string;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  evidence_count?: number;
  evidence_files?: EvidenceFile[];
  audit_logs?: AuditLog[];
}

export interface CaseCreatePayload {
  case_number: string;
  case_name: string;
  investigator: string;
  description?: string;
}

export interface CaseUpdatePayload {
  case_name?: string;
  investigator?: string;
  description?: string;
  status?: CaseStatus;
}

export interface BlockDeviceInfo {
  name: string;
  path: string;
  size: string;
  size_bytes?: number;
  model?: string;
  vendor?: string;
  transport?: string;
  removable?: boolean;
}
