import { FolderLock, Plus, HardDrive, ArrowRight, ShieldCheck, FileCode2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/card";
import { useCaseStore } from "../stores/useCaseStore";
import { useNavigate } from "react-router-dom";

export function CasesPage() {
  const navigate = useNavigate();
  const setActiveCase = useCaseStore((s) => s.setActiveCase);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
            <FolderLock className="size-7 text-primary" />
            Forensic Cases Hub
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage evidence files, create new case dossiers, or select an active case for
            investigation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => {
              setActiveCase("case-demo-1351", "CAS-2026-001", "Downtown Jewelry Heist");
              navigate("/investigate");
            }}
            className="gap-2"
          >
            <Plus className="size-4" />
            New Case
          </Button>
        </div>
      </div>

      {/* Quick Intake Callout for Scenario 1 / Scenario 2 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <HardDrive className="size-4 text-primary" />
                Physical Drive Ingestion
              </CardTitle>
            </div>
            <CardDescription>
              Clone physical CCTV/DVR block devices with streaming SHA-256 / MD5 hashing via dc3dd.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                setActiveCase("case-demo-1351", "CAS-2026-001", "Downtown Jewelry Heist");
                navigate("/investigate");
              }}
            >
              Open Intake Wizard →
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <FileCode2 className="size-4 text-cyan-400" />
                Raw Disk Image Ingestion
              </CardTitle>
            </div>
            <CardDescription>
              Directly ingest raw .dd, .raw, or .bin forensic images with automatic proprietary
              signature detection.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                setActiveCase("case-demo-1351", "CAS-2026-001", "Downtown Jewelry Heist");
                navigate("/investigate");
              }}
            >
              Select Image File →
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="size-4 text-emerald-400" />
                Audit Trail & Chain of Custody
              </CardTitle>
            </div>
            <CardDescription>
              Courtroom-grade immutable audit logs recording every acquisition, offset calibration,
              and export.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => navigate("/audit")}
            >
              View Audit Ledger →
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Active / Existing Cases Grid */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold font-heading flex items-center gap-2">
          <span>Active Investigation Cases</span>
          <span className="text-xs font-mono font-normal bg-secondary px-2 py-0.5 rounded text-muted-foreground">
            1 Available
          </span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-2xl bg-card border border-border hover:border-primary/50 transition-all space-y-4 group">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                  CAS-2026-001
                </span>
                <h3 className="text-base font-semibold mt-1.5">Downtown Jewelry Store Heist</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  4-Channel Dahua NVR with overwritten index sectors and clock drift.
                </p>
              </div>

              <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                ACTIVE
              </span>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-border/60 text-xs text-muted-foreground font-mono">
              <div className="flex items-center gap-4">
                <span>4 Cameras</span>
                <span>•</span>
                <span>12 Carved Clips</span>
                <span>•</span>
                <span>88 AI Detections</span>
              </div>

              <Button
                size="sm"
                className="gap-1.5 group-hover:bg-primary group-hover:text-primary-foreground"
                onClick={() => {
                  setActiveCase("case-demo-1351", "CAS-2026-001", "Downtown Jewelry Heist");
                  navigate("/investigate");
                }}
              >
                Open Case
                <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
