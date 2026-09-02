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
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useCaseStore } from "../stores/useCaseStore";
import { CameraTile } from "../components/player/CameraTile";
import { TimelineScrubber } from "../components/player/TimelineScrubber";
import { CalibrationModal } from "../components/player/CalibrationModal";
import { useQuery } from "@tanstack/react-query";
import { casesApi } from "../api/cases";
import { videoApi } from "../api/video";
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

  // 1. Fetch case details to find attached evidence
  const { data: caseDetails } = useQuery({
    queryKey: ["case", activeCaseId],
    queryFn: () => (activeCaseId ? casesApi.getCase(activeCaseId) : null),
    enabled: !!activeCaseId,
  });

  // Auto-select first evidence file if not yet active
  useEffect(() => {
    if (caseDetails?.evidence_files && caseDetails.evidence_files.length > 0) {
      if (!activeEvidenceId) {
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

  const activeClipsCount = Object.keys(cameraClipsMap).length;

  const handleCarveAll = async () => {
    if (!activeEvidenceId || isCarving) return;
    try {
      setIsCarving(true);
      await videoApi.carveAllClips({ evidence_id: activeEvidenceId });
      // Poll for completion
      const interval = setInterval(async () => {
        const res = await refetchClips();
        if (res.data?.clips && res.data.clips.length > 0) {
          clearInterval(interval);
          setIsCarving(false);
        }
      }, 2000);
      setTimeout(() => {
        clearInterval(interval);
        setIsCarving(false);
      }, 30000);
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
    </div>
  );
}
