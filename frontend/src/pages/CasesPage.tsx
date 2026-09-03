import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  FolderLock,
  Plus,
  HardDrive,
  ArrowRight,
  ShieldCheck,
  FileCode2,
  Search,
  RefreshCw,
  FolderOpen,
  Calendar,
  User,
  Film,
  Pencil,
  Trash2,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/card";
import { CreateCaseModal } from "../components/cases/CreateCaseModal";
import { EvidenceIntakeModal } from "../components/cases/EvidenceIntakeModal";
import { EditCaseModal } from "../components/cases/EditCaseModal";
import { DeleteCaseModal } from "../components/cases/DeleteCaseModal";
import { casesApi } from "../api/cases";
import { useCaseStore } from "../stores/useCaseStore";
import { queryClient } from "../lib/query-client";
import type { Case, CaseStatus } from "../types/case";
import { format } from "date-fns";

const formatLocalDate = (dateStr?: string | null): string => {
  if (!dateStr) return "N/A";
  try {
    const normalized = dateStr.endsWith("Z") || dateStr.includes("+") ? dateStr : `${dateStr}Z`;
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return "N/A";
    return format(d, "yyyy-MM-dd hh:mm a");
  } catch {
    return "N/A";
  }
};

export function CasesPage() {
  const navigate = useNavigate();
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const setActiveCase = useCaseStore((s) => s.setActiveCase);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<CaseStatus | "ALL">("ALL");
  const [createModalOpen, setCreateModalOpen] = useState<boolean>(false);
  const [intakeModalOpen, setIntakeModalOpen] = useState<boolean>(false);
  const [targetCaseForIntake, setTargetCaseForIntake] = useState<{
    id: string;
    caseNumber: string;
  } | null>(null);
  const [editingCase, setEditingCase] = useState<Case | null>(null);
  const [deletingCase, setDeletingCase] = useState<Case | null>(null);

  const runningTasks = useCaseStore((s) => s.runningTasks);
  const activeIntakeState = useCaseStore((s) => s.activeIntakeState);

  // Auto-restore Evidence Intake modal ONLY if an ingestion is ACTIVELY in progress (PROCESSING or PENDING)
  useEffect(() => {
    if (activeIntakeState && !intakeModalOpen) {
      const matchingTask = runningTasks.find((t) => t.task_id === activeIntakeState.taskId);
      if (
        matchingTask &&
        matchingTask.status !== "PROCESSING" &&
        matchingTask.status !== "PENDING"
      ) {
        useCaseStore.getState().setActiveIntakeState(null);
        return;
      }
      queueMicrotask(() => {
        setTargetCaseForIntake({
          id: activeIntakeState.caseId,
          caseNumber: activeIntakeState.caseNumber,
        });
        setIntakeModalOpen(true);
      });
    }
  }, [activeIntakeState, runningTasks, intakeModalOpen]);

  // TanStack Query for live case list
  const {
    data: cases = [],
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ["cases", selectedStatus === "ALL" ? undefined : selectedStatus],
    queryFn: () => casesApi.listCases(selectedStatus === "ALL" ? undefined : selectedStatus),
  });

  const filteredCases = cases.filter((c) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.case_number.toLowerCase().includes(q) ||
      c.case_name.toLowerCase().includes(q) ||
      c.investigator.toLowerCase().includes(q)
    );
  });

  const handleOpenCase = (c: Case) => {
    setActiveCase(c.id, c.case_number, c.case_name);
    navigate("/investigate");
  };

  const handleCaseCreated = (newCase: Case) => {
    void queryClient.invalidateQueries({ queryKey: ["cases"] });
    setActiveCase(newCase.id, newCase.case_number, newCase.case_name);

    // Prompt immediate evidence intake (Scenario 1: Day 1 Guided Flow)
    setTargetCaseForIntake({
      id: newCase.id,
      caseNumber: newCase.case_number,
    });
    setIntakeModalOpen(true);
  };

  const handleOpenIntakeForCase = (c: Case) => {
    setActiveCase(c.id, c.case_number, c.case_name);
    setTargetCaseForIntake({
      id: c.id,
      caseNumber: c.case_number,
    });
    setIntakeModalOpen(true);
  };

  return (
    <div className="p-6 md:p-8 w-full space-y-6 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-heading tracking-tight flex items-center gap-3">
            <FolderLock className="size-7 text-primary" />
            Forensic Cases Hub
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Standardized CCTV/DVR forensic management, physical acquisition, and evidence dossier
            repository.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isRefetching}
            className="gap-1.5"
            title="Refresh case list"
          >
            <RefreshCw className={`size-3.5 ${isRefetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            onClick={() => setCreateModalOpen(true)}
            className="gap-2 shadow-md shadow-primary/20 font-semibold"
          >
            <Plus className="size-4" />
            New Case Dossier
          </Button>
        </div>
      </div>

      {/* Quick Intake Actions Callout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <HardDrive className="size-4 text-primary" />
              Physical Disk Cloning (dc3dd)
            </CardTitle>
            <CardDescription>
              Direct hardware block-device acquisition with streaming SHA-256 / MD5 hashing and
              write-block parity.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                if (cases.length > 0) {
                  handleOpenIntakeForCase(cases[0]);
                } else {
                  setCreateModalOpen(true);
                }
              }}
            >
              Start Disk Imaging →
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileCode2 className="size-4 text-cyan-400" />
              Raw Disk Image Ingestion
            </CardTitle>
            <CardDescription>
              Ingest raw .dd / .raw bitstream files with proprietary magic byte detection (Dahua,
              Hikvision, WFS).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                if (cases.length > 0) {
                  handleOpenIntakeForCase(cases[0]);
                } else {
                  setCreateModalOpen(true);
                }
              }}
            >
              Ingest Image File →
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border hover:border-primary/50 transition-colors">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldCheck className="size-4 text-emerald-400" />
              Chain of Custody & Audit
            </CardTitle>
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
              Inspect Audit Trail →
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-2">
        <div className="relative w-full md:w-80">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by case number, title, officer..."
            className="pl-9 text-xs"
          />
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1 bg-secondary/80 p-1 rounded-xl border border-border">
          {(["ALL", "ACTIVE", "ARCHIVED", "CLOSED"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setSelectedStatus(st)}
              className={`px-3 py-1 rounded-lg text-xs font-mono transition-all ${
                selectedStatus === st
                  ? "bg-card text-foreground font-semibold shadow-xs border border-border/60"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Cases List Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold font-heading flex items-center gap-2">
            <span>Investigation Dossiers</span>
            <span className="text-xs font-mono font-normal bg-secondary px-2 py-0.5 rounded text-muted-foreground">
              {filteredCases.length} Dossier{filteredCases.length === 1 ? "" : "s"}
            </span>
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-48 rounded-2xl border border-border bg-card/30">
            <div className="flex items-center gap-3 text-muted-foreground text-sm font-mono">
              <RefreshCw className="size-4 animate-spin text-primary" />
              <span>Loading forensic dossiers from database...</span>
            </div>
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 rounded-2xl border border-border/80 bg-card/20 text-center p-6 space-y-3">
            <FolderOpen className="size-10 text-muted-foreground/40" />
            <h3 className="text-base font-semibold">No forensic cases found</h3>
            <p className="text-xs text-muted-foreground max-w-sm">
              {searchQuery
                ? `No cases match the query "${searchQuery}".`
                : "Create a new case dossier to ingest CCTV evidence images and start carving."}
            </p>
            <Button size="sm" onClick={() => setCreateModalOpen(true)} className="gap-2">
              <Plus className="size-3.5" />
              Create First Case
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-4">
            {filteredCases.map((c) => {
              const isCurrentActive = c.id === activeCaseId;
              const evidenceCount = c.evidence_count ?? 0;

              return (
                <div
                  key={c.id}
                  className={`p-5 rounded-2xl bg-card border transition-all space-y-4 group ${
                    isCurrentActive
                      ? "border-primary ring-1 ring-primary/30 shadow-md shadow-primary/5"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                          {c.case_number}
                        </span>
                        {isCurrentActive && (
                          <span className="text-[10px] font-mono font-bold bg-primary text-primary-foreground px-1.5 py-0.5 rounded">
                            ACTIVE
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-semibold mt-1.5">{c.case_name}</h3>
                      {c.description && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {c.description}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`text-xs font-mono px-2 py-0.5 rounded-full border ${
                          c.status === "ACTIVE"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : c.status === "ARCHIVED"
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                              : "bg-muted text-muted-foreground border-border"
                        }`}
                      >
                        {c.status}
                      </span>

                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingCase(c);
                        }}
                        className="text-muted-foreground hover:text-foreground hover:bg-secondary size-7"
                        title="Edit Case Dossier"
                      >
                        <Pencil className="size-3.5" />
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingCase(c);
                        }}
                        className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 size-7"
                        title="Delete Case Dossier"
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </div>

                  {/* Metadata Chips */}
                  <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground font-mono">
                    <div className="flex items-center gap-1.5">
                      <User className="size-3.5 text-primary" />
                      <span>{c.investigator}</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Calendar className="size-3.5" />
                      <span>{formatLocalDate(c.created_at)}</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Film className="size-3.5 text-cyan-400" />
                      <span>
                        {evidenceCount} Evidence File{evidenceCount === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>

                  {/* Card Actions */}
                  <div className="flex items-center justify-between pt-3 border-t border-border/60">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => handleOpenIntakeForCase(c)}
                      className="gap-1 text-xs"
                    >
                      <HardDrive className="size-3" />+ Add Evidence
                    </Button>

                    <Button
                      size="sm"
                      onClick={() => handleOpenCase(c)}
                      className="gap-1.5 font-semibold group-hover:bg-primary group-hover:text-primary-foreground"
                    >
                      Open Case
                      <ArrowRight className="size-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modals */}
      <CreateCaseModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onCaseCreated={handleCaseCreated}
      />

      <EditCaseModal
        open={!!editingCase}
        onOpenChange={(open) => !open && setEditingCase(null)}
        caseItem={editingCase}
        onSuccess={() => refetch()}
      />

      <DeleteCaseModal
        open={!!deletingCase}
        onOpenChange={(open) => !open && setDeletingCase(null)}
        caseItem={deletingCase}
        onSuccess={() => {
          refetch();
          queryClient.invalidateQueries({ queryKey: ["cases"] });
        }}
      />

      {targetCaseForIntake && (
        <EvidenceIntakeModal
          open={intakeModalOpen}
          onOpenChange={setIntakeModalOpen}
          caseId={targetCaseForIntake.id}
          caseNumber={targetCaseForIntake.caseNumber}
        />
      )}
    </div>
  );
}
