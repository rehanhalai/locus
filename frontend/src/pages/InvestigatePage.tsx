import { useState, useMemo, useEffect } from "react";
import {
  Grid2X2,
  LayoutTemplate,
  Square,
  Radio,
  FolderOpen,
  RefreshCw,
  HardDrive,
  Zap,
  CheckCircle2,
  Clock,
  AlertCircle,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { useCaseStore } from "../stores/useCaseStore";
import { CameraTile } from "../components/player/CameraTile";
import { TimelineScrubber } from "../components/player/TimelineScrubber";
import { CalibrationModal } from "../components/player/CalibrationModal";
import { useQuery } from "@tanstack/react-query";
import { casesApi } from "../api/cases";
import { videoApi } from "../api/video";
import { subscribeSSE } from "../api/sse";
import { useNavigate } from "react-router-dom";
import type { CarvedClip } from "../types/video";

type LayoutMode = "GRID_2X2" | "FOCUS_1X3" | "SINGLE";

const DEFAULT_CAMERA_LABELS: Record<number, string> = {
  1: "Main Entrance",
  2: "Cash Counter",
  3: "Vault Area",
  4: "Street Perimeter",
};

export function InvestigatePage() {
  const navigate = useNavigate();
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("GRID_2X2");
  const [calibrationModalOpen, setCalibrationModalOpen] = useState(false);
  const [calibratingCameraId, setCalibratingCameraId] = useState(1);

  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const activeEvidenceId = useCaseStore((s) => s.activeEvidenceId);
  const setActiveEvidenceId = useCaseStore((s) => s.setActiveEvidenceId);
  const focusedCameraId = useCaseStore((s) => s.focusedCameraId);
  const setFocusedCameraId = useCaseStore((s) => s.setFocusedCameraId);
  const setTimelineBounds = useCaseStore((s) => s.setTimelineBounds);
  const setMasterPlayheadTime = useCaseStore((s) => s.setMasterPlayheadTime);
  const masterPlayheadTime = useCaseStore((s) => s.masterPlayheadTime);
  const runningTasks = useCaseStore((s) => s.runningTasks);
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);
  const removeTask = useCaseStore((s) => s.removeTask);
  const [isModalDismissed, setIsModalDismissed] = useState(false);

  const activeCarveTask = runningTasks.find(
    (t) =>
      (t.type === "carving" || t.task_id.startsWith("carve_")) &&
      (t.status === "PROCESSING" || t.status === "PENDING")
  );

  const setActiveCase = useCaseStore((s) => s.setActiveCase);

  // Auto-discover valid cases
  const { data: casesList } = useQuery({
    queryKey: ["cases"],
    queryFn: () => casesApi.listCases(),
  });

  // Auto-heal active case if current activeCaseId is stale/deleted
  useEffect(() => {
    if (casesList && casesList.length > 0) {
      const exists = casesList.some((c) => c.id === activeCaseId);
      if (!activeCaseId || !exists) {
        const fallback = casesList[casesList.length - 1];
        setActiveCase(fallback.id, fallback.case_number, fallback.case_name);
      }
    }
  }, [casesList, activeCaseId, setActiveCase]);

  // 1. Fetch case details to find attached evidence
  const { data: caseDetails } = useQuery({
    queryKey: ["case", activeCaseId],
    queryFn: () => (activeCaseId ? casesApi.getCase(activeCaseId) : null),
    enabled: !!activeCaseId,
  });

  // Auto-select valid evidence file if current activeEvidenceId is stale or not in case
  useEffect(() => {
    if (caseDetails?.evidence_files && caseDetails.evidence_files.length > 0) {
      const evExists = caseDetails.evidence_files.some((e) => e.id === activeEvidenceId);
      if (!activeEvidenceId || !evExists) {
        setActiveEvidenceId(caseDetails.evidence_files[0].id);
      }
    }
  }, [caseDetails, activeEvidenceId, setActiveEvidenceId]);

  // 2. Fetch carved clips for active evidence
  const {
    data: carvedData,
    isLoading: isClipsLoading,
    refetch: refetchClips,
  } = useQuery({
    queryKey: ["carved-clips", activeEvidenceId],
    queryFn: () => (activeEvidenceId ? videoApi.getCarvedClips(activeEvidenceId) : null),
    enabled: !!activeEvidenceId,
  });

  const [isCarving, setIsCarving] = useState(false);

  // Map clips to camera channel IDs
  const cameraClipsMap = useMemo(() => {
    const map: Record<number, CarvedClip> = {};
    if (carvedData?.clips) {
      carvedData.clips.forEach((clip) => {
        // If multiple clips exist for a camera, store the latest or first
        if (!map[clip.camera_id]) {
          map[clip.camera_id] = clip;
        }
      });
    }
    return map;
  }, [carvedData]);

  // Synchronize master timeline bounds to match the carved evidence duration
  useEffect(() => {
    if (carvedData?.clips && carvedData.clips.length > 0) {
      const times = carvedData.clips.flatMap((c) => [
        new Date(c.start_time).getTime(),
        new Date(c.end_time).getTime(),
      ]);
      const validTimes = times.filter((t) => !isNaN(t));
      if (validTimes.length > 0) {
        const minT = Math.min(...validTimes);
        const maxT = Math.max(...validTimes);
        const startIso = new Date(minT).toISOString();
        const endIso = new Date(maxT).toISOString();
        setTimelineBounds(startIso, endIso);

        const currentMs = new Date(masterPlayheadTime).getTime();
        if (isNaN(currentMs) || currentMs < minT || currentMs > maxT) {
          setMasterPlayheadTime(startIso);
        }
      }
    }
  }, [carvedData, setTimelineBounds, setMasterPlayheadTime, masterPlayheadTime]);

  const activeClipsCount = Object.keys(cameraClipsMap).length;

  // Auto-clean any stale carving task if all feeds are already carved and available
  useEffect(() => {
    if (activeClipsCount > 0 && activeCarveTask && !isCarving) {
      removeTask(activeCarveTask.task_id);
    }
  }, [activeClipsCount, activeCarveTask, isCarving, removeTask]);

  // Direct SSE listener for the carving task
  useEffect(() => {
    if (!activeCarveTask?.task_id) return;

    const unsub = subscribeSSE<{
      type?: string;
      status?: string;
      stage?: string;
      percent?: number;
      progress_percent?: number;
      percentage?: number;
      message?: string;
    }>(`/carver/progress/${activeCarveTask.task_id}`, {
      onMessage: (data) => {
        const pct = data.percent ?? data.progress_percent ?? data.percentage;
        const isDone =
          data.type === "COMPLETED" ||
          data.status === "COMPLETED" ||
          data.stage === "COMPLETED" ||
          (pct !== undefined && pct >= 100);

        addOrUpdateTask({
          task_id: activeCarveTask.task_id,
          type: "carving",
          title: "Multi-Camera Video Carving",
          status: isDone ? "COMPLETED" : "PROCESSING",
          progress_percent:
            pct !== undefined ? Math.min(100, Math.round(pct)) : (activeCarveTask.progress_percent || 10),
          message: data.message || "Carving camera streams...",
          started_at: activeCarveTask.started_at,
        });

        if (isDone) {
          setIsCarving(false);
          refetchClips();
        }
      },
      onComplete: () => {
        setIsCarving(false);
        refetchClips();
      },
      onError: () => {
        // Fallback refetch in case task ended
        refetchClips();
      },
    });

    return () => unsub();
  }, [activeCarveTask?.task_id, addOrUpdateTask, refetchClips]);

  // Auto-refresh feeds when carving task completes
  useEffect(() => {
    if (!activeCarveTask && isCarving) {
      setIsCarving(false);
      refetchClips();
    }
  }, [activeCarveTask, isCarving, refetchClips]);

  const handleCarveAll = async () => {
    if (!activeEvidenceId || isCarving) return;
    try {
      setIsCarving(true);
      setIsModalDismissed(false);
      const res = await videoApi.carveAllClips({ evidence_id: activeEvidenceId });
      if (res?.task_id) {
        addOrUpdateTask({
          task_id: res.task_id,
          type: "carving",
          title: "Multi-Camera Video Carving",
          status: "PROCESSING",
          progress_percent: 5,
          message: "Scanning FAT32 directory & demuxing packets...",
          started_at: new Date().toISOString(),
        });
      }
    } catch {
      setIsCarving(false);
    }
  };

  const handleTileFocusToggle = (camId: number) => {
    if (layoutMode === "SINGLE" && focusedCameraId === camId) {
      setLayoutMode("GRID_2X2");
      setFocusedCameraId(null);
    } else {
      setFocusedCameraId(camId);
      setLayoutMode("SINGLE");
    }
  };

  const primaryCamId = focusedCameraId || 1;
  const secondaryCamIds = [1, 2, 3, 4].filter((id) => id !== primaryCamId);

  // If no case is selected, prompt investigator
  if (!activeCaseId) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center space-y-4 bg-background select-none">
        <div className="p-4 rounded-2xl bg-secondary/40 border border-border">
          <FolderOpen className="size-12 text-primary" />
        </div>
        <div className="max-w-md space-y-1.5">
          <h2 className="text-xl font-bold tracking-tight">No Active Forensic Dossier</h2>
          <p className="text-xs text-muted-foreground">
            Please open an existing investigation case from Case Hub to analyze multi-camera feeds
            and synchronized timelines.
          </p>
        </div>
        <Button onClick={() => navigate("/cases")} className="gap-2">
          <HardDrive className="size-4" />
          Open Case Hub [Hotkey: 0]
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* Investigation Room Sub-Header */}
      <div className="h-12 border-b border-border/80 bg-card/60 backdrop-blur-md px-4 flex items-center justify-between gap-4 shrink-0">
        {/* Left: Case Info & Live Signal Badge */}
        <div className="flex items-center gap-3 min-w-0">
          <Badge
            variant="outline"
            className="font-mono text-[11px] bg-primary/10 border-primary/30 text-primary shrink-0"
          >
            {activeCaseNumber || activeCaseId.slice(0, 8)}
          </Badge>
          <span className="text-xs font-semibold truncate text-foreground/90">
            {activeCaseName || "Forensic Incident Review"}
          </span>

          <div className="h-4 w-[1px] bg-border hidden sm:block" />

          <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground">
            <Radio className="size-3 text-emerald-400 animate-pulse" />
            <span>{activeClipsCount} / 4 Channels Online</span>
          </div>
        </div>

        {/* Right: Layout Mode Switchers & Refresh */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-secondary/80 p-0.5 rounded-lg border border-border">
            <Button
              variant={layoutMode === "GRID_2X2" ? "default" : "ghost"}
              size="icon-xs"
              onClick={() => {
                setLayoutMode("GRID_2X2");
                setFocusedCameraId(null);
              }}
              title="2x2 Multi-Cam Grid Layout"
            >
              <Grid2X2 className="size-3.5" />
            </Button>
            <Button
              variant={layoutMode === "FOCUS_1X3" ? "default" : "ghost"}
              size="icon-xs"
              onClick={() => {
                setLayoutMode("FOCUS_1X3");
                if (!focusedCameraId) setFocusedCameraId(1);
              }}
              title="1+3 Focus Layout"
            >
              <LayoutTemplate className="size-3.5" />
            </Button>
            <Button
              variant={layoutMode === "SINGLE" ? "default" : "ghost"}
              size="icon-xs"
              onClick={() => {
                setLayoutMode("SINGLE");
                if (!focusedCameraId) setFocusedCameraId(1);
              }}
              title="Single Full-View Layout"
            >
              <Square className="size-3.5" />
            </Button>
          </div>

          {activeEvidenceId && activeClipsCount === 0 && (
            <Button
              variant="default"
              size="xs"
              onClick={handleCarveAll}
              disabled={isCarving}
              className="gap-1.5 text-xs font-semibold shadow-xs"
              title="Carve video streams from ingested disk image"
            >
              <Zap
                className={`size-3.5 ${isCarving ? "animate-spin text-amber-400" : "fill-current"}`}
              />
              {isCarving ? "Carving Feeds..." : "Carve Streams"}
            </Button>
          )}

          <Button
            variant="outline"
            size="icon-xs"
            onClick={() => refetchClips()}
            title="Refresh Video Feeds"
          >
            <RefreshCw className={`size-3.5 ${isClipsLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Main Multi-Cam Viewport Grid */}
      <div className="flex-1 p-2.5 min-h-0 overflow-hidden bg-black/40">
        {layoutMode === "GRID_2X2" && (
          <div className="grid grid-cols-2 grid-rows-2 gap-2.5 h-full w-full">
            {[1, 2, 3, 4].map((camId) => (
              <CameraTile
                key={camId}
                cameraId={camId}
                channelName={DEFAULT_CAMERA_LABELS[camId] || `Camera ${camId}`}
                clip={cameraClipsMap[camId] || null}
                isFocused={focusedCameraId === camId}
                onToggleFocus={() => handleTileFocusToggle(camId)}
                onOpenCalibration={() => {
                  setCalibratingCameraId(camId);
                  setCalibrationModalOpen(true);
                }}
              />
            ))}
          </div>
        )}

        {layoutMode === "FOCUS_1X3" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5 h-full w-full">
            {/* Main Primary View (2 Columns) */}
            <div className="md:col-span-2 h-full">
              <CameraTile
                cameraId={primaryCamId}
                channelName={DEFAULT_CAMERA_LABELS[primaryCamId] || `Camera ${primaryCamId}`}
                clip={cameraClipsMap[primaryCamId] || null}
                isFocused={true}
                onToggleFocus={() => handleTileFocusToggle(primaryCamId)}
                onOpenCalibration={() => {
                  setCalibratingCameraId(primaryCamId);
                  setCalibrationModalOpen(true);
                }}
              />
            </div>

            {/* Side Thumbnail Feeds (1 Column Stack) */}
            <div className="flex flex-col gap-2.5 h-full overflow-hidden">
              {secondaryCamIds.map((camId) => (
                <div key={camId} className="flex-1 min-h-0">
                  <CameraTile
                    cameraId={camId}
                    channelName={DEFAULT_CAMERA_LABELS[camId] || `Camera ${camId}`}
                    clip={cameraClipsMap[camId] || null}
                    isFocused={false}
                    onToggleFocus={() => handleTileFocusToggle(camId)}
                    onOpenCalibration={() => {
                      setCalibratingCameraId(camId);
                      setCalibrationModalOpen(true);
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {layoutMode === "SINGLE" && (
          <div className="h-full w-full">
            <CameraTile
              cameraId={primaryCamId}
              channelName={DEFAULT_CAMERA_LABELS[primaryCamId] || `Camera ${primaryCamId}`}
              clip={cameraClipsMap[primaryCamId] || null}
              isFocused={true}
              onToggleFocus={() => handleTileFocusToggle(primaryCamId)}
              onOpenCalibration={() => {
                setCalibratingCameraId(primaryCamId);
                setCalibrationModalOpen(true);
              }}
            />
          </div>
        )}
      </div>

      {/* Master Timeline Scrubber & Synchronized Playhead */}
      <TimelineScrubber
        clips={carvedData?.clips || []}
        onOpenCalibration={() => {
          setCalibratingCameraId(1);
          setCalibrationModalOpen(true);
        }}
      />
      {/* Clock Drift Calibration Modal */}
      <CalibrationModal
        open={calibrationModalOpen}
        onOpenChange={setCalibrationModalOpen}
        evidenceId={activeEvidenceId || ""}
        initialCameraId={calibratingCameraId}
      />

      {/* Active Carving Progress Modal Overlay */}
      {!isModalDismissed && (isCarving || activeCarveTask) && activeClipsCount === 0 && (
        <div className="absolute inset-0 z-50 bg-background/85 backdrop-blur-md flex items-center justify-center p-6 animate-in fade-in duration-200 select-none">
          <div className="w-full max-w-lg bg-card border border-border shadow-2xl rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="size-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                  <Radio className="size-5 animate-pulse text-primary" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-base font-bold tracking-tight text-foreground flex items-center gap-2">
                    <span>Carving Video Feeds</span>
                    <span className="font-mono text-primary text-sm font-semibold">
                      {activeCarveTask?.progress_percent || 10}%
                    </span>
                  </h3>
                  <p className="text-xs text-muted-foreground truncate">
                    Demuxing raw DVR packets & generating H.264 streams
                  </p>
                </div>
              </div>
              <Button
                size="icon-xs"
                variant="ghost"
                onClick={() => setIsModalDismissed(true)}
                className="text-muted-foreground hover:text-foreground shrink-0"
                title="Dismiss overlay"
              >
                <X className="size-4" />
              </Button>
            </div>

            {/* Glowing Animated Progress Bar */}
            <div className="space-y-2">
              <Progress
                value={activeCarveTask?.progress_percent || 10}
                className="h-2.5 bg-secondary"
              />
              <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                <span className="flex items-center gap-1.5 text-foreground/90 font-medium truncate">
                  <RefreshCw className="size-3 animate-spin text-primary shrink-0" />
                  {activeCarveTask?.message || "Transcoding elementary video streams..."}
                </span>
              </div>
            </div>

            {/* Camera Channels Status Grid */}
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-border/60">
              {[
                { id: 1, name: "Main Entrance" },
                { id: 2, name: "Cash Counter" },
                { id: 3, name: "Vault Area" },
                { id: 4, name: "Street Perimeter" },
              ].map((c) => {
                const isDone = (activeCarveTask?.progress_percent || 0) >= (c.id * 20 + 15);
                const isCurrent =
                  !isDone &&
                  (activeCarveTask?.message?.includes(`Camera ${c.id}`) ||
                    (activeCarveTask?.progress_percent || 0) >= ((c.id - 1) * 20 + 10));

                return (
                  <div
                    key={c.id}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg border text-xs font-mono transition-colors ${
                      isDone
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                        : isCurrent
                          ? "bg-primary/10 border-primary/40 text-primary ring-1 ring-primary/20"
                          : "bg-secondary/40 border-border/60 text-muted-foreground/60"
                    }`}
                  >
                    <span className="truncate">CH {c.id} · {c.name}</span>
                    {isDone ? (
                      <CheckCircle2 className="size-3.5 text-emerald-400 shrink-0" />
                    ) : isCurrent ? (
                      <RefreshCw className="size-3 animate-spin text-primary shrink-0" />
                    ) : (
                      <Clock className="size-3 text-muted-foreground/40 shrink-0" />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Forensic Safe Notice */}
            <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-2.5 flex items-start gap-2 text-[11px] text-amber-300">
              <AlertCircle className="size-4 shrink-0 text-amber-400 mt-0.5" />
              <span>
                Please do not close or reload. Elementary NAL units are being transcoded with static keyframes (<code className="font-mono text-amber-200">+faststart</code>) for smooth timeline scrubbing.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
