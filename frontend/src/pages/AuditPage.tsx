import {
  ScrollText,
  Download,
  RefreshCw,
  ShieldCheck,
  AlertCircle,
  Clock,
  User,
} from "lucide-react";
import { Button } from "../components/ui/button";
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
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";

const formatUtcTimestamp = (dateStr?: string | null): string => {
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

const getActionBadgeColor = (action: string) => {
  switch (action) {
    case "CASE_CREATED":
      return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    case "CASE_INGESTION":
    case "INGESTION_COMPLETED":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    case "DEVICE_IDENTIFIED":
      return "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
    case "HEADER_PARSED":
      return "bg-purple-500/10 text-purple-400 border-purple-500/20";
    case "VIDEO_CARVED":
      return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    case "CALIBRATION_APPLIED":
    case "TIMELINE_CALIBRATED":
      return "bg-indigo-500/10 text-indigo-400 border-indigo-500/20";
    case "ANALYTICS_PROCESSED":
      return "bg-violet-500/10 text-violet-400 border-violet-500/20";
    case "EVIDENCE_EXPORTED":
    case "EXPORT_VERIFIED":
      return "bg-primary/10 text-primary border-primary/20";
    default:
      return "bg-muted text-muted-foreground border-border";
  }
};

export function AuditPage() {
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const investigatorName = useCaseStore((s) => s.investigatorName);

  const {
    data: logs = [],
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ["auditLogs", activeCaseId],
    queryFn: () => (activeCaseId ? casesApi.getCaseAuditLogs(activeCaseId) : Promise.resolve([])),
    enabled: !!activeCaseId,
    refetchInterval: 5000,
  });

  const handleDownloadPdf = () => {
    if (!activeCaseId) return;
    const url = exportApi.getPdfDownloadUrl(activeCaseId, investigatorName);
    window.open(url, "_blank");
  };

  return (
    <div className="p-6 md:p-8 w-full space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
            <ScrollText className="size-7 text-primary" />
            Immutable Forensic Audit Trail Ledger
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Tamper-evident chain of custody recording every cryptographic event, user calibration,
            and export
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

          <Button
            onClick={handleDownloadPdf}
            disabled={!activeCaseId}
            className="gap-2 shadow-md shadow-primary/20"
          >
            <Download className="size-4" />
            Download Official Courtroom PDF Dossier
          </Button>
        </div>
      </div>

      {!activeCaseId ? (
        <div className="p-12 text-center rounded-2xl border border-dashed border-border/80 bg-card/50">
          <AlertCircle className="size-10 text-muted-foreground mx-auto mb-3 opacity-60" />
          <h3 className="text-base font-semibold text-foreground">No Case Selected</h3>
          <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
            Please select an active case from Room 1 (Cases) to view its immutable cryptographic
            audit trail.
          </p>
        </div>
      ) : (
        /* Audit Log Table */
        <div className="rounded-xl border border-border overflow-hidden bg-card shadow-sm">
          <Table>
            <TableHeader className="bg-secondary/70">
              <TableRow className="border-border">
                <TableHead className="py-3 px-4 w-16 font-mono text-xs text-muted-foreground">
                  #
                </TableHead>
                <TableHead className="py-3 px-4 w-48 font-mono text-xs text-muted-foreground">
                  Timestamp (UTC)
                </TableHead>
                <TableHead className="py-3 px-4 w-52 font-mono text-xs text-muted-foreground">
                  Action / Event
                </TableHead>
                <TableHead className="py-3 px-4 w-44 font-mono text-xs text-muted-foreground">
                  Officer / Actor
                </TableHead>
                <TableHead className="py-3 px-4 font-mono text-xs text-muted-foreground">
                  Details & Cryptographic Proof
                </TableHead>
                <TableHead className="py-3 px-4 w-28 font-mono text-xs text-muted-foreground text-center">
                  Integrity
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="font-mono text-xs">
              {isLoading ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="py-12 text-center text-muted-foreground font-sans"
                  >
                    <RefreshCw className="size-5 animate-spin mx-auto mb-2 text-primary" />
                    Loading verified audit ledger...
                  </TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="py-12 text-center text-muted-foreground font-sans"
                  >
                    <Clock className="size-6 mx-auto mb-2 opacity-40" />
                    No audit records registered yet for this case.
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow
                    key={log.id}
                    className="border-border/60 hover:bg-muted/30 transition-colors"
                  >
                    <TableCell className="py-3.5 px-4 font-bold text-muted-foreground">
                      {log.id}
                    </TableCell>
                    <TableCell className="py-3.5 px-4 text-foreground font-mono">
                      {formatUtcTimestamp(log.timestamp)}
                    </TableCell>
                    <TableCell className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded border text-[11px] font-bold ${getActionBadgeColor(
                          log.action
                        )}`}
                      >
                        {log.action}
                      </span>
                    </TableCell>
                    <TableCell className="py-3.5 px-4 text-muted-foreground font-sans">
                      <span className="flex items-center gap-1.5">
                        <User className="size-3 text-muted-foreground/70" />
                        {log.actor || "Forensic Officer"}
                      </span>
                    </TableCell>
                    <TableCell className="py-3.5 px-4 text-foreground font-sans break-all">
                      {log.details || "Action recorded"}
                    </TableCell>
                    <TableCell className="py-3.5 px-4 text-center font-sans">
                      <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                        <ShieldCheck className="size-3" />
                        {log.integrity_status || "VERIFIED"}
                      </span>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
