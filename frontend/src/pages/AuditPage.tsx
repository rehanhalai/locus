import { ScrollText, Download } from "lucide-react";
import { Button } from "../components/ui/button";
import { exportApi } from "../api/export";
import { useCaseStore } from "../stores/useCaseStore";

export function AuditPage() {
  const activeCaseId = useCaseStore((s) => s.activeCaseId);

  const mockLogs = [
    {
      id: "001",
      timestamp: "2026-08-30 14:00:00 UTC",
      action: "CASE_CREATED",
      investigator: "Officer Sharma",
      details: "Case CAS-2026-001 initialized with 4 camera channels.",
    },
    {
      id: "002",
      timestamp: "2026-08-30 14:00:15 UTC",
      action: "INGESTION_COMPLETED",
      investigator: "System Engine",
      details: "SHA-256: 8f4c3a1e9b2c8d7... Sealed authentic.",
    },
    {
      id: "003",
      timestamp: "2026-08-30 14:00:20 UTC",
      action: "DEVICE_IDENTIFIED",
      investigator: "System Engine",
      details: "Dahua DHFS v2.0 magic bytes matched (Confidence: 100%).",
    },
    {
      id: "004",
      timestamp: "2026-08-30 14:00:35 UTC",
      action: "HEADER_PARSED",
      investigator: "System Engine",
      details: "Parsed 48 frame sectors. Master sector map created.",
    },
    {
      id: "005",
      timestamp: "2026-08-30 14:02:10 UTC",
      action: "CALIBRATION_APPLIED",
      investigator: "Investigator Pande",
      details: "Cam 2 clock offset +12.5s applied to correct NVR drift.",
    },
    {
      id: "006",
      timestamp: "2026-08-30 14:06:45 UTC",
      action: "EVIDENCE_EXPORTED",
      investigator: "Investigator Pande",
      details: "Exported suspect_counter_1402_1406.mp4 with HMAC .sync.json sidecar.",
    },
  ];

  const handleDownloadPdf = () => {
    if (!activeCaseId) return;
    const url = exportApi.getPdfDownloadUrl(activeCaseId);
    window.open(url, "_blank");
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
            <ScrollText className="size-7 text-primary" />
            Immutable Forensic Audit Trail Ledger
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Tamper-evident chain of custody recording every cryptographic event, user calibration, and export.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button onClick={handleDownloadPdf} className="gap-2 shadow-md shadow-primary/20">
            <Download className="size-4" />
            Download Official Courtroom PDF Dossier
          </Button>
        </div>
      </div>

      {/* Audit Log Table matching Excalidraw */}
      <div className="rounded-xl border border-border overflow-hidden bg-card">
        <table className="w-full text-left text-xs">
          <thead className="bg-secondary/70 border-b border-border text-muted-foreground font-mono">
            <tr>
              <th className="py-3 px-4 w-16">Log #</th>
              <th className="py-3 px-4 w-48">Timestamp (UTC)</th>
              <th className="py-3 px-4 w-52">Action / Event</th>
              <th className="py-3 px-4 w-44">Investigator</th>
              <th className="py-3 px-4">Details & Proof</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60 font-mono">
            {mockLogs.map((log) => (
              <tr key={log.id} className="hover:bg-muted/30 transition-colors">
                <td className="py-3.5 px-4 font-bold text-muted-foreground">{log.id}</td>
                <td className="py-3.5 px-4 text-foreground">{log.timestamp}</td>
                <td className="py-3.5 px-4">
                  <span className="px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20 font-bold">
                    {log.action}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-muted-foreground">{log.investigator}</td>
                <td className="py-3.5 px-4 text-foreground font-sans">{log.details}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
