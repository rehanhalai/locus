import { useState, useMemo, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Search,
  Filter,
  Play,
  Sparkles,
  User,
  Car,
  Briefcase,
  Activity,
  RotateCcw,
  Clock,
  Camera,
  RefreshCw,
  X,
  Zap,
  Maximize2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import { useCaseStore } from "../stores/useCaseStore";
import { analyticsApi } from "../api/analytics";
import { casesApi } from "../api/cases";
import type { TimelineEvent } from "../types/analytics";

const CAMERA_LABELS: Record<number, string> = {
  1: "Main Entrance",
  2: "Cash Counter",
  3: "Vault Area",
  4: "Street Perimeter",
};

const PAGE_SIZE = 24;

export function SearchPage() {
  const navigate = useNavigate();
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeEvidenceId = useCaseStore((s) => s.activeEvidenceId);
  const setActiveEvidenceId = useCaseStore((s) => s.setActiveEvidenceId);
  const setMasterPlayheadTime = useCaseStore((s) => s.setMasterPlayheadTime);
  const setFocusedCameraId = useCaseStore((s) => s.setFocusedCameraId);
  const setIsPlaying = useCaseStore((s) => s.setIsPlaying);
  const runningTasks = useCaseStore((s) => s.runningTasks);
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);

  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

  // Filter states
  const [selectedClass, setSelectedClass] = useState<string>("all");
  const [selectedCamera, setSelectedCamera] = useState<number | "all">("all");
  const [minConfidence, setMinConfidence] = useState<number>(0.35);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [selectedEventForLightbox, setSelectedEventForLightbox] = useState<TimelineEvent | null>(
    null
  );

  // Reset page when filters change
  const handleClassChange = (cls: string) => {
    setSelectedClass(cls);
    setPage(1);
  };
  const handleCameraChange = (cam: number | "all") => {
    setSelectedCamera(cam);
    setPage(1);
  };
  const handleConfidenceChange = (conf: number) => {
    setMinConfidence(conf);
    setPage(1);
  };

  // AI run dialog state
  const [isRunDialogOpen, setIsRunDialogOpen] = useState<boolean>(false);
  const [runConfidence, setRunConfidence] = useState<number>(0.35);
  const [runMotionGating, setRunMotionGating] = useState<boolean>(true);
  const [runTargetClasses, setRunTargetClasses] = useState<string[]>([
    "person",
    "car",
    "truck",
    "backpack",
  ]);

  // Check if AI detection task is actively running
  const activeAiTask = runningTasks.find(
    (t) =>
      (t.type === "analytics" || t.task_id.startsWith("task_ai_")) &&
      (t.status === "PROCESSING" || t.status === "PENDING")
  );

  // Auto-discover valid evidence if none selected
  const { data: caseDetails } = useQuery({
    queryKey: ["case", activeCaseId],
    queryFn: () => (activeCaseId ? casesApi.getCase(activeCaseId) : null),
    enabled: !!activeCaseId,
  });

  useEffect(() => {
    if (caseDetails?.evidence_files && caseDetails.evidence_files.length > 0) {
      const exists = caseDetails.evidence_files.some((e) => e.id === activeEvidenceId);
      if (!activeEvidenceId || !exists) {
        setActiveEvidenceId(caseDetails.evidence_files[0].id);
      }
    }
  }, [caseDetails, activeEvidenceId, setActiveEvidenceId]);

  // Derive target label list for backend query
  const queryLabels = useMemo(() => {
    if (selectedClass === "all") return undefined;
    if (selectedClass === "person") return ["person"];
    if (selectedClass === "vehicle") return ["car", "truck", "bus", "motorcycle", "bicycle"];
    if (selectedClass === "bag") return ["backpack", "handbag", "suitcase"];
    if (selectedClass === "motion") return ["motion", "motion_void"];
    return [selectedClass];
  }, [selectedClass]);

  // Query paginated AI timeline events from backend
  const {
    data: eventsResponse,
    isLoading: isLoadingEvents,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: [
      "analytics-events",
      activeEvidenceId,
      selectedCamera,
      queryLabels,
      minConfidence,
      page,
    ],
    queryFn: () => {
      if (!activeEvidenceId) return null;
      return analyticsApi.searchEvents(activeEvidenceId, {
        camera_id: selectedCamera === "all" ? undefined : selectedCamera,
        labels: queryLabels,
        min_confidence: minConfidence,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
    },
    enabled: !!activeEvidenceId,
    refetchInterval: activeAiTask ? 3000 : false,
  });

  const totalEvents = eventsResponse?.total_events || 0;
  const events = useMemo<TimelineEvent[]>(() => eventsResponse?.events || [], [eventsResponse]);
  const totalPages = Math.max(1, Math.ceil(totalEvents / PAGE_SIZE));

  // Client-side instant keyword search on current page
  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return events;
    const q = searchQuery.toLowerCase();
    return events.filter((evt) => {
      const camLabel = CAMERA_LABELS[evt.camera_id]?.toLowerCase() || "";
      const labelName = evt.label.toLowerCase();
      return labelName.includes(q) || camLabel.includes(q);
    });
  }, [events, searchQuery]);

  // Handle triggering AI Analytics
  const handleStartAnalytics = async () => {
    if (!activeEvidenceId) return;
    try {
      setIsRunDialogOpen(false);
      const res = await analyticsApi.startAnalytics({
        evidence_id: activeEvidenceId,
        confidence_threshold: runConfidence,
        motion_gating: runMotionGating,
        target_classes: runTargetClasses,
      });

      if (res?.task_id) {
        addOrUpdateTask({
          task_id: res.task_id,
          type: "analytics",
          title: "YOLOv8 Video Intelligence",
          status: "PROCESSING",
          progress_percent: 5,
          message: "Initiating motion gating & neural network inference...",
          started_at: new Date().toISOString(),
        });
      }
    } catch (err) {
      console.error("Failed to start analytics:", err);
    }
  };

  // Cross-Room Deep Linking: Jump to playhead in Room 1
  const handleJumpToPlayhead = (event: TimelineEvent) => {
    setMasterPlayheadTime(event.timestamp);
    setFocusedCameraId(event.camera_id);
    setIsPlaying(true);
    navigate("/investigate");
  };

  return (
    <div className="flex h-full overflow-hidden bg-background select-none">
      {/* 1. Left-Hand Filter Sidebar */}
      <div className="w-72 border-r border-border/80 bg-card/30 flex flex-col shrink-0">
        <div className="p-4 border-b border-border/60 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="size-4 text-primary" />
            <h2 className="text-sm font-semibold tracking-tight">Intelligence Filters</h2>
          </div>
          {(selectedClass !== "all" ||
            selectedCamera !== "all" ||
            minConfidence !== 0.35 ||
            searchQuery !== "") && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => {
                handleClassChange("all");
                handleCameraChange("all");
                handleConfidenceChange(0.35);
                setSearchQuery("");
              }}
              title="Reset filters"
              className="text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="size-3.5" />
            </Button>
          )}
        </div>

        <div className="p-4 space-y-6 overflow-y-auto flex-1 text-xs">
          {/* Search keyword input */}
          <div className="space-y-1.5">
            <label className="font-mono text-muted-foreground uppercase text-[10px] tracking-wider">
              Search Detections
            </label>
            <div className="relative">
              <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter by label or camera..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-background/60 border border-border/80 rounded-lg focus:outline-none focus:border-primary/80 transition-colors"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>

          {/* Target Object Classes */}
          <div className="space-y-2">
            <label className="font-mono text-muted-foreground uppercase text-[10px] tracking-wider">
              Target Classes
            </label>
            <div className="grid grid-cols-1 gap-1.5">
              <button
                onClick={() => handleClassChange("all")}
                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all ${
                  selectedClass === "all"
                    ? "bg-primary/10 border-primary/40 text-primary font-medium"
                    : "bg-card/40 border-border/60 hover:bg-accent/40 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Sparkles className="size-3.5" />
                  <span>All Objects</span>
                </div>
              </button>

              <button
                onClick={() => handleClassChange("person")}
                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all ${
                  selectedClass === "person"
                    ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400 font-medium"
                    : "bg-card/40 border-border/60 hover:bg-accent/40 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <User className="size-3.5 text-emerald-400" />
                  <span>Persons / Suspects</span>
                </div>
              </button>

              <button
                onClick={() => handleClassChange("vehicle")}
                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all ${
                  selectedClass === "vehicle"
                    ? "bg-sky-500/10 border-sky-500/40 text-sky-400 font-medium"
                    : "bg-card/40 border-border/60 hover:bg-accent/40 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Car className="size-3.5 text-sky-400" />
                  <span>Vehicles</span>
                </div>
              </button>

              <button
                onClick={() => handleClassChange("bag")}
                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all ${
                  selectedClass === "bag"
                    ? "bg-amber-500/10 border-amber-500/40 text-amber-400 font-medium"
                    : "bg-card/40 border-border/60 hover:bg-accent/40 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Briefcase className="size-3.5 text-amber-400" />
                  <span>Bags & Luggage</span>
                </div>
              </button>

              <button
                onClick={() => handleClassChange("motion")}
                className={`flex items-center justify-between px-3 py-2 rounded-lg border text-left transition-all ${
                  selectedClass === "motion"
                    ? "bg-purple-500/10 border-purple-500/40 text-purple-400 font-medium"
                    : "bg-card/40 border-border/60 hover:bg-accent/40 text-muted-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Activity className="size-3.5 text-purple-400" />
                  <span>Motion Voids</span>
                </div>
              </button>
            </div>
          </div>

          {/* Camera Channel Filter */}
          <div className="space-y-2">
            <label className="font-mono text-muted-foreground uppercase text-[10px] tracking-wider">
              Camera Channel
            </label>
            <div className="grid grid-cols-1 gap-1">
              <button
                onClick={() => handleCameraChange("all")}
                className={`px-3 py-1.5 rounded-lg text-left transition-colors ${
                  selectedCamera === "all"
                    ? "bg-primary/10 text-primary font-semibold"
                    : "text-muted-foreground hover:bg-accent/30"
                }`}
              >
                All Cameras
              </button>
              {[1, 2, 3, 4].map((camId) => (
                <button
                  key={camId}
                  onClick={() => handleCameraChange(camId)}
                  className={`px-3 py-1.5 rounded-lg text-left transition-colors flex items-center justify-between ${
                    selectedCamera === camId
                      ? "bg-primary/10 text-primary font-semibold"
                      : "text-muted-foreground hover:bg-accent/30"
                  }`}
                >
                  <span className="truncate">
                    CH {camId} · {CAMERA_LABELS[camId] || `Cam ${camId}`}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Confidence Slider */}
          <div className="space-y-2 pt-2 border-t border-border/60">
            <div className="flex items-center justify-between">
              <label className="font-mono text-muted-foreground uppercase text-[10px] tracking-wider">
                Min Confidence
              </label>
              <span className="font-mono text-primary font-bold">
                {Math.round(minConfidence * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0.25"
              max="0.95"
              step="0.05"
              value={minConfidence}
              onChange={(e) => handleConfidenceChange(parseFloat(e.target.value))}
              className="w-full accent-primary h-1.5 bg-secondary rounded-lg cursor-pointer"
            />
          </div>
        </div>
      </div>

      {/* 2. Main Investigation Workspace */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Workspace Header */}
        <div className="h-14 border-b border-border/80 px-6 flex items-center justify-between bg-card/20 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
              <Sparkles className="size-4" />
            </div>
            <div className="min-w-0">
              <h1 className="text-sm font-bold tracking-tight text-foreground flex items-center gap-2">
                <span>Room 2: AI Video Intelligence & Object Detection</span>
                {activeCaseNumber && (
                  <Badge variant="outline" className="font-mono text-[10px] uppercase">
                    {activeCaseNumber}
                  </Badge>
                )}
              </h1>
              <p className="text-[11px] text-muted-foreground truncate">
                {activeCaseName || "No active case"} · Visual Frame Inspector with YOLOv8 Bounding
                Boxes
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchEvents()}
              disabled={isLoadingEvents}
              className="gap-1.5"
            >
              <RefreshCw className={`size-3.5 ${isLoadingEvents ? "animate-spin" : ""}`} />
              Refresh
            </Button>

            <Button
              variant="default"
              size="sm"
              onClick={() => setIsRunDialogOpen(true)}
              disabled={!activeEvidenceId || Boolean(activeAiTask)}
              className="gap-1.5 shadow-sm shadow-primary/20"
            >
              <Zap className="size-3.5 fill-primary-foreground" />
              Run AI Analytics
            </Button>
          </div>
        </div>

        {/* Live Task Banner (If processing) */}
        {activeAiTask && (
          <div className="px-6 py-3 bg-primary/10 border-b border-primary/20 flex items-center justify-between text-xs animate-in fade-in duration-200">
            <div className="flex items-center gap-3">
              <RefreshCw className="size-4 animate-spin text-primary shrink-0" />
              <div>
                <span className="font-semibold text-foreground">Neural Inference in Progress</span>
                <span className="text-muted-foreground ml-2">
                  {activeAiTask.message || "Running YOLOv8 object detection across carved clips..."}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-32 bg-secondary/80 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-primary h-full transition-all duration-300"
                  style={{ width: `${activeAiTask.progress_percent || 10}%` }}
                />
              </div>
              <span className="font-mono font-bold text-primary">
                {activeAiTask.progress_percent || 10}%
              </span>
            </div>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Results Header */}
          <div className="flex items-center justify-between border-b border-border/60 pb-2">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-mono uppercase text-muted-foreground tracking-wider flex items-center gap-2">
                <span>Matching Detections ({totalEvents.toLocaleString()})</span>
                {selectedClass !== "all" && (
                  <Badge variant="secondary" className="capitalize text-[10px]">
                    {selectedClass}
                  </Badge>
                )}
                {selectedCamera !== "all" && (
                  <Badge variant="secondary" className="text-[10px]">
                    CH {selectedCamera}
                  </Badge>
                )}
              </h3>
            </div>

            {/* Pagination controls in header */}
            {totalPages > 1 && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground font-mono text-[11px]">
                  Page {page} of {totalPages}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={page <= 1 || isLoadingEvents}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft className="size-3.5" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon-xs"
                    disabled={page >= totalPages || isLoadingEvents}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    <ChevronRight className="size-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Empty State: No Detections Run Yet */}
          {totalEvents === 0 && !isLoadingEvents && (
            <div className="py-16 text-center space-y-4 border border-dashed border-border/80 rounded-2xl bg-card/20">
              <div className="size-12 rounded-2xl bg-primary/10 text-primary mx-auto flex items-center justify-center">
                <Sparkles className="size-6" />
              </div>
              <div className="space-y-1">
                <h4 className="text-base font-semibold text-foreground">
                  No detection events match current filter settings
                </h4>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                  Try lowering the confidence threshold or selecting &quot;All Objects&quot;, or run
                  YOLOv8 neural analytics over the carved footage.
                </p>
              </div>
              <Button
                variant="default"
                size="sm"
                onClick={() => setIsRunDialogOpen(true)}
                className="gap-2"
              >
                <Zap className="size-3.5 fill-primary-foreground" />
                Run AI Detection Now
              </Button>
            </div>
          )}

          {/* Detections Visual Event Grid */}
          {filteredEvents.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredEvents.map((evt) => {
                const camName = CAMERA_LABELS[evt.camera_id] || `Camera ${evt.camera_id}`;
                const dateObj = new Date(evt.timestamp);
                const timeStr = isNaN(dateObj.getTime())
                  ? evt.timestamp
                  : dateObj.toISOString().replace("T", " ").substring(11, 23) + " UTC";

                const isPerson = evt.label === "person";
                const isVehicle = ["car", "truck", "bus", "motorcycle", "bicycle"].includes(
                  evt.label
                );
                const isBag = ["backpack", "handbag", "suitcase"].includes(evt.label);
                const frameUrl = `${apiBase}/analytics/events/${evt.id}/frame?draw_bbox=true`;

                return (
                  <div
                    key={evt.id}
                    className="rounded-xl bg-card border border-border/70 hover:border-primary/50 transition-all overflow-hidden flex flex-col group shadow-xs hover:shadow-lg"
                  >
                    {/* Visual Frame Container with Bounding Box Overlay */}
                    <div className="relative aspect-[4/3] bg-black/90 overflow-hidden flex items-center justify-center">
                      <img
                        src={frameUrl}
                        alt={`${evt.label} detection`}
                        loading="lazy"
                        className="w-full h-full object-cover group-hover:scale-103 transition-transform duration-300"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = "none";
                        }}
                      />

                      {/* Top Overlay: Camera Badge + Confidence Pill */}
                      <div className="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none">
                        <Badge
                          variant="secondary"
                          className="font-mono text-[10px] font-semibold gap-1 bg-black/70 backdrop-blur-md text-white border-white/20"
                        >
                          <Camera className="size-3 text-primary" />
                          CH {evt.camera_id} · {camName}
                        </Badge>

                        <Badge
                          variant="outline"
                          className={`capitalize font-mono text-[10px] gap-1 font-semibold backdrop-blur-md ${
                            isPerson
                              ? "bg-emerald-950/80 border-emerald-500/50 text-emerald-400"
                              : isVehicle
                                ? "bg-sky-950/80 border-sky-500/50 text-sky-400"
                                : isBag
                                  ? "bg-amber-950/80 border-amber-500/50 text-amber-400"
                                  : "bg-purple-950/80 border-purple-500/50 text-purple-400"
                          }`}
                        >
                          {isPerson && <User className="size-3" />}
                          {isVehicle && <Car className="size-3" />}
                          {isBag && <Briefcase className="size-3" />}
                          {!isPerson && !isVehicle && !isBag && <Activity className="size-3" />}
                          {evt.label} · {Math.round(evt.confidence * 100)}%
                        </Badge>
                      </div>

                      {/* Hover Action Overlays: Inspect Lightbox Button */}
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                        <Button
                          size="xs"
                          variant="secondary"
                          onClick={() => setSelectedEventForLightbox(evt)}
                          className="gap-1 shadow-md bg-background/90 text-foreground hover:bg-background"
                          title="View High-Res Frame"
                        >
                          <Maximize2 className="size-3.5" />
                          Enlarge
                        </Button>

                        <Button
                          size="xs"
                          variant="default"
                          onClick={() => handleJumpToPlayhead(evt)}
                          className="gap-1 shadow-md"
                          title="Jump to timeline playhead in Room 1"
                        >
                          <Play className="size-3 fill-primary-foreground" />
                          Jump to Playhead
                        </Button>
                      </div>

                      {/* Bottom-right: Frame Index Badge */}
                      {evt.frame_number !== undefined && (
                        <div className="absolute bottom-1.5 right-2 font-mono text-[10px] text-white/70 bg-black/60 px-1.5 py-0.5 rounded pointer-events-none">
                          Frame #{evt.frame_number}
                        </div>
                      )}
                    </div>

                    {/* Card Footer: Timestamp & Action Controls */}
                    <div className="p-3 bg-card/60 flex items-center justify-between border-t border-border/40 text-xs">
                      <div className="flex items-center gap-1.5 text-muted-foreground font-mono text-[11px]">
                        <Clock className="size-3 text-muted-foreground/80" />
                        <span>{timeStr}</span>
                      </div>

                      <Button
                        size="xs"
                        variant="ghost"
                        onClick={() => handleJumpToPlayhead(evt)}
                        className="gap-1 text-primary hover:text-primary hover:bg-primary/10 h-7 text-[11px]"
                      >
                        <Play className="size-3 fill-primary" />
                        Jump to Playhead
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Bottom Pagination controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border/60 pt-4 text-xs">
              <span className="text-muted-foreground font-mono text-[11px]">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, totalEvents)} of{" "}
                {totalEvents.toLocaleString()} detections
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1 || isLoadingEvents}
                  onClick={() => {
                    setPage((p) => Math.max(1, p - 1));
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className="gap-1"
                >
                  <ChevronLeft className="size-3.5" />
                  Previous
                </Button>
                <span className="font-mono text-xs px-2">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages || isLoadingEvents}
                  onClick={() => {
                    setPage((p) => Math.min(totalPages, p + 1));
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className="gap-1"
                >
                  Next
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. High-Resolution Frame Lightbox Dialog */}
      <Dialog
        open={Boolean(selectedEventForLightbox)}
        onOpenChange={(open) => !open && setSelectedEventForLightbox(null)}
      >
        <DialogContent className="max-w-2xl bg-card border-border shadow-2xl rounded-2xl p-6 space-y-4">
          {selectedEventForLightbox && (
            <>
              <DialogHeader>
                <div className="flex items-center justify-between">
                  <DialogTitle className="flex items-center gap-2 text-base font-bold tracking-tight">
                    <Camera className="size-4 text-primary" />
                    <span>
                      CH {selectedEventForLightbox.camera_id} ·{" "}
                      {CAMERA_LABELS[selectedEventForLightbox.camera_id] ||
                        `Camera ${selectedEventForLightbox.camera_id}`}
                    </span>
                  </DialogTitle>
                  <Badge
                    variant="outline"
                    className="capitalize font-mono text-xs font-semibold bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  >
                    {selectedEventForLightbox.label} ·{" "}
                    {Math.round(selectedEventForLightbox.confidence * 100)}% Confidence
                  </Badge>
                </div>
                <DialogDescription className="text-xs text-muted-foreground font-mono">
                  Timestamp: {selectedEventForLightbox.timestamp} · Frame #
                  {selectedEventForLightbox.frame_number ?? 0}
                </DialogDescription>
              </DialogHeader>

              {/* Full Resolution Frame Image */}
              <div className="relative aspect-[4/3] bg-black rounded-xl overflow-hidden border border-border/80 flex items-center justify-center">
                <img
                  src={`${apiBase}/analytics/events/${selectedEventForLightbox.id}/frame?draw_bbox=true`}
                  alt="Enlarged forensic detection frame"
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Forensic Bounding Box Metadata Details */}
              <div className="p-3 rounded-xl bg-secondary/30 border border-border/60 grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">
                    Bounding Box Coordinates
                  </span>
                  <span className="text-foreground font-semibold">
                    X: {selectedEventForLightbox.bbox_x?.toFixed(4)} · Y:{" "}
                    {selectedEventForLightbox.bbox_y?.toFixed(4)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">
                    Box Dimensions (W × H)
                  </span>
                  <span className="text-foreground font-semibold">
                    W: {selectedEventForLightbox.bbox_w?.toFixed(4)} · H:{" "}
                    {selectedEventForLightbox.bbox_h?.toFixed(4)}
                  </span>
                </div>
              </div>

              <DialogFooter className="flex items-center justify-between pt-2 border-t border-border/60">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedEventForLightbox(null)}
                >
                  Close
                </Button>
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={() => {
                    const evt = selectedEventForLightbox;
                    setSelectedEventForLightbox(null);
                    handleJumpToPlayhead(evt);
                  }}
                  className="gap-1.5"
                >
                  <Play className="size-3.5 fill-primary-foreground" />
                  Jump to Playhead in Room 1
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 4. Run AI Analytics Configuration Dialog */}
      <Dialog open={isRunDialogOpen} onOpenChange={setIsRunDialogOpen}>
        <DialogContent className="max-w-md bg-card border-border shadow-2xl rounded-2xl p-6 space-y-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold tracking-tight">
              <Zap className="size-5 text-primary" />
              Configure AI Video Intelligence
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Run offline YOLOv8 neural network inference and OpenCV MOG2 motion gating over carved
              camera clips.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            {/* Confidence Threshold */}
            <div className="space-y-2">
              <div className="flex items-center justify-between font-mono">
                <span className="text-muted-foreground">Detection Confidence Threshold</span>
                <span className="text-primary font-bold">{Math.round(runConfidence * 100)}%</span>
              </div>
              <input
                type="range"
                min="0.20"
                max="0.80"
                step="0.05"
                value={runConfidence}
                onChange={(e) => setRunConfidence(parseFloat(e.target.value))}
                className="w-full accent-primary h-1.5 bg-secondary rounded-lg cursor-pointer"
              />
              <p className="text-[11px] text-muted-foreground">
                Higher threshold reduces false positives; lower threshold catches distant suspects.
              </p>
            </div>

            {/* Motion Gating Switch */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-secondary/30 border border-border/60">
              <div className="space-y-0.5">
                <div className="font-semibold text-foreground flex items-center gap-1.5">
                  <Activity className="size-3.5 text-primary" />
                  MOG2 Motion Gating (10x Speedup)
                </div>
                <div className="text-[11px] text-muted-foreground">
                  Skip inactive empty scenes without running heavy neural inferences.
                </div>
              </div>
              <input
                type="checkbox"
                checked={runMotionGating}
                onChange={(e) => setRunMotionGating(e.target.checked)}
                className="size-4 rounded border-border text-primary focus:ring-primary cursor-pointer"
              />
            </div>

            {/* Target Classes Selection */}
            <div className="space-y-2">
              <label className="font-mono text-muted-foreground uppercase text-[10px] tracking-wider">
                Target Object Classes
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "person", label: "Persons / Suspects", icon: User },
                  { id: "car", label: "Automobiles", icon: Car },
                  { id: "truck", label: "Trucks & Vans", icon: Car },
                  { id: "backpack", label: "Backpacks & Bags", icon: Briefcase },
                ].map((item) => {
                  const isChecked = runTargetClasses.includes(item.id);
                  const Icon = item.icon;
                  return (
                    <label
                      key={item.id}
                      className={`flex items-center gap-2 p-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                        isChecked
                          ? "bg-primary/10 border-primary/40 text-foreground font-medium"
                          : "bg-secondary/20 border-border/40 text-muted-foreground hover:bg-secondary/40"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setRunTargetClasses([...runTargetClasses, item.id]);
                          } else {
                            setRunTargetClasses(runTargetClasses.filter((c) => c !== item.id));
                          }
                        }}
                        className="rounded border-border text-primary size-3.5"
                      />
                      <Icon className="size-3 text-primary" />
                      <span className="truncate">{item.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>

          <DialogFooter className="flex items-center justify-between pt-2 border-t border-border/60">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsRunDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleStartAnalytics}
              className="gap-1.5"
            >
              <Zap className="size-3.5 fill-primary-foreground" />
              Start YOLOv8 Analysis
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
