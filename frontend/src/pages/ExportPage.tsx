import { useState } from "react";
import {
  Scale,
  Lock,
  Download,
  FileText,
  CheckCircle2,
  ShieldCheck,
  RefreshCw,
  Archive,
  AlertCircle,
  Film,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "../components/ui/table";
import { exportApi } from "../api/export";
import { casesApi } from "../api/cases";
import { useCaseStore } from "../stores/useCaseStore";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";

const formatLocalDate = (dateStr?: string | null): string => {
  if (!dateStr) return "N/A";
  try {
    const normalized = dateStr.endsWith("Z") || dateStr.includes("+") ? dateStr : `${dateStr}Z`;
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return dateStr;
    return `${format(d, "yyyy-MM-dd HH:mm:ss")} UTC`;
  } catch {
    return dateStr;
  }
};

export function ExportPage() {
  const queryClient = useQueryClient();
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const activeEvidenceId = useCaseStore((s) => s.activeEvidenceId);
  const investigatorName = useCaseStore((s) => s.investigatorName);

  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<number>(1);
  const [startTime, setStartTime] = useState<string>("2026-08-30T10:00:00Z");
  const [endTime, setEndTime] = useState<string>("2026-08-30T10:05:00Z");
  const [reason, setReason] = useState<string>("Suspect identified in critical timeline window");
  const [zeroTranscode, setZeroTranscode] = useState<boolean>(true);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  // Fetch case details for active evidence files
  const { data: caseDetails } = useQuery({
    queryKey: ["case", activeCaseId],
    queryFn: () => (activeCaseId ? casesApi.getCase(activeCaseId) : null),
    enabled: !!activeCaseId,
  });

  // Target evidence ID (fallback to first evidence in case if activeEvidenceId is null)
  const targetEvidenceId =
    activeEvidenceId || (caseDetails?.evidence_files && caseDetails.evidence_files[0]?.id) || null;

  // Live export list query
  const {
    data: exports = [],
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ["exports", activeCaseId],
    queryFn: () => (activeCaseId ? exportApi.listCaseExports(activeCaseId) : Promise.resolve([])),
    enabled: !!activeCaseId,
    refetchInterval: 6000,
  });

  // Mutation to export new time slice
  const exportSliceMutation = useMutation({
    mutationFn: () => {
      if (!targetEvidenceId) {
        throw new Error("No evidence file attached to the current case.");
      }
      setExportError(null);
      setExportSuccess(null);
      return exportApi.exportSlice({
        evidence_id: targetEvidenceId,
        camera_id: Number(selectedCamera),
        start_time:
          startTime.includes("Z") || startTime.includes("+") ? startTime : `${startTime}Z`,
        end_time: endTime.includes("Z") || endTime.includes("+") ? endTime : `${endTime}Z`,
        investigator: investigatorName || "Forensic Officer",
        reason: reason.trim() || undefined,
      });
    },
    onSuccess: (data) => {
      setExportSuccess(`Successfully sealed and exported ${data.exported_filename}`);
      queryClient.invalidateQueries({ queryKey: ["exports", activeCaseId] });
      queryClient.invalidateQueries({ queryKey: ["auditLogs", activeCaseId] });
    },
    onError: (err) => {
      setExportError(err?.message || "Failed to slice and seal evidence.");
    },
  });

  const handleCopy = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleDownload = (url?: string) => {
    if (!url) return;
    window.open(url, "_blank");
  };

  return (
    <div className="p-6 md:p-8 w-full space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
            <Scale className="size-7 text-primary" />
            Evidence Export & Cryptographic Hashing
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Perform zero-transcode time slicing, compute HMAC-signed sidecar receipts, and export
            court-ready evidence bundles
            {activeCaseNumber ? (
              <span className="text-foreground font-semibold">
                {" "}
                for Case {activeCaseNumber} ({activeCaseName || "Active"})
              </span>
            ) : null}
            .
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || isRefetching || !activeCaseId}
            className="gap-1.5"
          >
            <RefreshCw className={`size-3.5 ${isRefetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {!activeCaseId ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-border/80 bg-card/50">
          <AlertCircle className="size-10 text-muted-foreground mx-auto mb-3 opacity-60" />
          <h3 className="text-base font-semibold text-foreground">No Case Selected</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
            Please select an active case from Room 1 (Cases) to slice and seal evidence.
          </p>
        </div>
      ) : (
        <>
          {/* Zone 1: Export & Seal Form */}
          <div className="p-6 rounded-2xl bg-card border border-border space-y-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold font-heading flex items-center gap-2">
                <Lock className="size-4 text-primary" />
                Export Time Slice & Seal Evidence
              </h2>
              {targetEvidenceId ? (
                <span className="text-xs font-mono text-muted-foreground bg-secondary/80 px-2.5 py-1 rounded-md border border-border">
                  Evidence:{" "}
                  <span className="text-foreground font-semibold">{targetEvidenceId}</span>
                </span>
              ) : (
                <span className="text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-md border border-amber-500/20">
                  No evidence file in case yet
                </span>
              )}
            </div>

            {exportError && (
              <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-xs rounded-lg flex items-center gap-2">
                <AlertCircle className="size-4 shrink-0" />
                {exportError}
              </div>
            )}

            {exportSuccess && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-lg flex items-center gap-2">
                <CheckCircle2 className="size-4 shrink-0" />
                {exportSuccess}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-mono text-muted-foreground">Camera Channel</label>
                <select
                  value={selectedCamera}
                  onChange={(e) => setSelectedCamera(Number(e.target.value))}
                  className="w-full bg-secondary border border-border text-xs rounded-lg px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value={1}>Channel 1 (Main Entrance)</option>
                  <option value={2}>Channel 2 (Cash Counter)</option>
                  <option value={3}>Channel 3 (Vault Area)</option>
                  <option value={4}>Channel 4 (Street Corner)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono text-muted-foreground">Start UTC Time</label>
                <Input
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  placeholder="YYYY-MM-DDTHH:MM:SSZ"
                  className="text-xs font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-mono text-muted-foreground">End UTC Time</label>
                <Input
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  placeholder="YYYY-MM-DDTHH:MM:SSZ"
                  className="text-xs font-mono"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-mono text-muted-foreground">
                Export Reason (Immutable Chain-of-Custody Audit Record)
              </label>
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Reason for slicing this segment..."
                className="text-xs"
              />
            </div>

            {/* Checkboxes */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={zeroTranscode}
                  onChange={(e) => setZeroTranscode(e.target.checked)}
                  className="rounded border-border text-primary"
                />
                <span>✓ Zero-Transcode Stream Copy (-c:v copy)</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked
                  disabled
                  className="rounded border-border text-primary"
                />
                <span>✓ Compute SHA-256 + HMAC .sync.json</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  defaultChecked
                  disabled
                  className="rounded border-border text-primary"
                />
                <span>✓ Commit Event to Legal Audit Ledger</span>
              </label>
            </div>

            <Button
              onClick={() => exportSliceMutation.mutate()}
              disabled={exportSliceMutation.isPending || !targetEvidenceId}
              className="w-full gap-2 font-semibold shadow-md shadow-primary/20 py-2.5"
            >
              {exportSliceMutation.isPending ? (
                <>
                  <RefreshCw className="size-4 animate-spin" />
                  SLICING, HASHING & CRYPTOGRAPHICALLY SEALING...
                </>
              ) : (
                <>
                  <Lock className="size-4" />
                  🔒 EXPORT & CRYPTOGRAPHICALLY SEAL EVIDENCE
                </>
              )}
            </Button>
          </div>

          {/* Zone 2: Manifest Table */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold font-heading flex items-center gap-2">
              <ShieldCheck className="size-5 text-emerald-400" />
              Case Evidence Manifest (Court-Ready Slices)
            </h2>

            <div className="rounded-xl border border-border overflow-hidden bg-card shadow-sm">
              <Table>
                <TableHeader className="bg-secondary/70">
                  <TableRow className="border-border font-mono text-muted-foreground text-xs">
                    <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground">
                      Exported Clip
                    </TableHead>
                    <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground">
                      Camera
                    </TableHead>
                    <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground">
                      Calibrated Time Range
                    </TableHead>
                    <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground">
                      SHA-256 Hash Fingerprint
                    </TableHead>
                    <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground text-right">
                      Legal Artifacts & Downloads
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-border/60 font-mono text-xs">
                  {isLoading ? (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="py-12 text-center text-muted-foreground font-sans"
                      >
                        <RefreshCw className="size-5 animate-spin mx-auto mb-2 text-primary" />
                        Loading sealed evidence manifest...
                      </TableCell>
                    </TableRow>
                  ) : exports.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="py-12 text-center text-muted-foreground font-sans"
                      >
                        <Film className="size-6 mx-auto mb-2 opacity-40" />
                        No sealed time slices exported yet for this case. Use the form above to
                        slice and seal an evidence clip.
                      </TableCell>
                    </TableRow>
                  ) : (
                    exports.map((exp) => (
                      <TableRow
                        key={exp.id}
                        className="border-border/60 hover:bg-muted/30 transition-colors"
                      >
                        <TableCell className="py-3.5 px-4 font-semibold text-foreground">
                          <div className="flex flex-col">
                            <span>{exp.exported_filename}</span>
                            <span className="text-[10px] text-muted-foreground font-sans mt-0.5">
                              Exported by: {exp.investigator || "Forensic Officer"}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="py-3.5 px-4 text-muted-foreground">
                          Cam {exp.camera_id}
                        </TableCell>
                        <TableCell className="py-3.5 px-4 text-primary">
                          {formatLocalDate(exp.start_time)} → {formatLocalDate(exp.end_time)}
                        </TableCell>
                        <TableCell className="py-3.5 px-4">
                          <button
                            onClick={() => handleCopy(exp.sha256_hash)}
                            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors truncate max-w-[200px] block font-mono"
                            title="Click to copy full SHA-256 hash"
                          >
                            {exp.sha256_hash ? (
                              <>
                                {exp.sha256_hash.slice(0, 16)}...{exp.sha256_hash.slice(-8)}
                                {copiedHash === exp.sha256_hash && (
                                  <span className="ml-1.5 text-emerald-400 font-bold">
                                    ✓ Copied!
                                  </span>
                                )}
                              </>
                            ) : (
                              "N/A"
                            )}
                          </button>
                        </TableCell>
                        <TableCell className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {exp.download_video_url && (
                              <Button
                                variant="outline"
                                size="xs"
                                onClick={() => handleDownload(exp.download_video_url)}
                                className="gap-1 hover:bg-primary/10 hover:text-primary"
                                title="Download zero-transcode MP4"
                              >
                                <Download className="size-3" />
                                .mp4
                              </Button>
                            )}
                            {exp.download_manifest_url && (
                              <Button
                                variant="outline"
                                size="xs"
                                onClick={() => handleDownload(exp.download_manifest_url)}
                                className="gap-1 hover:bg-cyan-500/10 hover:text-cyan-400"
                                title="Download .sync.json cryptographic manifest"
                              >
                                <FileText className="size-3 text-cyan-400" />
                                .json
                              </Button>
                            )}
                            {exp.download_bundle_url && (
                              <Button
                                variant="outline"
                                size="xs"
                                onClick={() => handleDownload(exp.download_bundle_url)}
                                className="gap-1 hover:bg-emerald-500/10 hover:text-emerald-400"
                                title="Download complete evidence ZIP bundle (video + manifest)"
                              >
                                <Archive className="size-3 text-emerald-400" />
                                .zip
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
