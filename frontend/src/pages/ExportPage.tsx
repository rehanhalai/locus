import { useState } from "react";
import { Scale, Lock, Download, FileText, CheckCircle2, ShieldCheck } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export function ExportPage() {
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const mockExports = [
    {
      id: "exp-1",
      filename: "suspect_counter_1402_1406.mp4",
      camera: "Cam 2 (Counter)",
      timeRange: "14:02:00 - 14:06:00",
      sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      size: "42.8 MB",
    },
    {
      id: "exp-2",
      filename: "entrance_suspect_1403_1405.mp4",
      camera: "Cam 1 (Entrance)",
      timeRange: "14:03:00 - 14:05:30",
      sha256: "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
      size: "28.4 MB",
    },
  ];

  const handleCopy = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-200">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
          <Scale className="size-7 text-primary" />
          Evidence Export & Cryptographic Hashing
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Perform zero-transcode time slicing, compute HMAC-signed sidecar receipts, and export court-ready evidence bundles.
        </p>
      </div>

      {/* Zone 1: Export & Seal Form matching Excalidraw */}
      <div className="p-6 rounded-2xl bg-card border border-border space-y-5">
        <h2 className="text-base font-semibold font-heading flex items-center gap-2">
          <Lock className="size-4 text-primary" />
          Export Time Slice & Seal Evidence
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-muted-foreground">Camera Channel</label>
            <select className="w-full bg-secondary border border-border text-xs rounded-lg px-3 py-2 text-foreground">
              <option value="2">Channel 2 (Cash Counter)</option>
              <option value="1">Channel 1 (Main Entrance)</option>
              <option value="3">Channel 3 (Vault Area)</option>
              <option value="4">Channel 4 (Street Corner)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-mono text-muted-foreground">Start UTC Time</label>
            <Input defaultValue="2026-08-30 14:02:00" className="text-xs font-mono" />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-mono text-muted-foreground">End UTC Time</label>
            <Input defaultValue="2026-08-30 14:06:00" className="text-xs font-mono" />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-mono text-muted-foreground">Export Reason (Audit Trail)</label>
          <Input
            defaultValue="Found suspicious activity matching suspect description"
            className="text-xs"
          />
        </div>

        {/* Checkboxes */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input type="checkbox" defaultChecked className="rounded border-border text-primary" />
            <span>✓ Zero-Transcode Stream Copy</span>
          </label>

          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input type="checkbox" defaultChecked className="rounded border-border text-primary" />
            <span>✓ Generate Cryptographic .sync.json</span>
          </label>

          <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
            <input type="checkbox" defaultChecked className="rounded border-border text-primary" />
            <span>✓ Generate Courtroom Summary Certificate</span>
          </label>
        </div>

        <Button className="w-full gap-2 font-semibold shadow-md shadow-primary/20">
          <Lock className="size-4" />
          🔒 EXPORT & CRYPTOGRAPHICALLY SEAL EVIDENCE
        </Button>
      </div>

      {/* Zone 2: Manifest Table matching Excalidraw */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold font-heading flex items-center gap-2">
          <ShieldCheck className="size-5 text-emerald-400" />
          Case Evidence Manifest (Court-Ready Clips)
        </h2>

        <div className="rounded-xl border border-border overflow-hidden bg-card">
          <table className="w-full text-left text-xs">
            <thead className="bg-secondary/70 border-b border-border text-muted-foreground font-mono">
              <tr>
                <th className="py-3 px-4">Exported Clip</th>
                <th className="py-3 px-4">Camera</th>
                <th className="py-3 px-4">Time Range</th>
                <th className="py-3 px-4">SHA-256 Hash Fingerprint</th>
                <th className="py-3 px-4 text-right">Legal Artifacts</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 font-mono">
              {mockExports.map((exp) => (
                <tr key={exp.id} className="hover:bg-muted/30 transition-colors">
                  <td className="py-3.5 px-4 font-semibold text-foreground">{exp.filename}</td>
                  <td className="py-3.5 px-4 text-muted-foreground">{exp.camera}</td>
                  <td className="py-3.5 px-4 text-primary">{exp.timeRange}</td>
                  <td className="py-3.5 px-4">
                    <button
                      onClick={() => handleCopy(exp.sha256)}
                      className="text-[11px] text-muted-foreground hover:text-foreground transition-colors truncate max-w-[200px] block"
                      title="Click to copy full SHA-256 hash"
                    >
                      {exp.sha256.slice(0, 16)}...{exp.sha256.slice(-8)}
                      {copiedHash === exp.sha256 && (
                        <span className="ml-1.5 text-emerald-400 font-bold">✓ Copied!</span>
                      )}
                    </button>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button variant="outline" size="xs" className="gap-1">
                        <Download className="size-3" />
                        .mp4
                      </Button>
                      <Button variant="outline" size="xs" className="gap-1">
                        <FileText className="size-3 text-cyan-400" />
                        .json
                      </Button>
                      <Button variant="outline" size="xs" className="gap-1">
                        <CheckCircle2 className="size-3 text-emerald-400" />
                        .pdf
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
