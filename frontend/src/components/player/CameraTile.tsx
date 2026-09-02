import React, { useEffect, useRef, useState } from "react";
import {
  Camera,
  Maximize2,
  Minimize2,
  Volume2,
  VolumeX,
  Clock,
  VideoOff,
  Radio,
  Expand,
  Shrink,
} from "lucide-react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { useCaseStore } from "../../stores/useCaseStore";
import type { CarvedClip } from "../../types/video";
import { format } from "date-fns";

interface CameraTileProps {
  cameraId: number;
  channelName: string;
  clip?: CarvedClip | null;
  isFocused?: boolean;
  onToggleFocus?: () => void;
  onOpenCalibration?: () => void;
}

export function CameraTile({
  cameraId,
  channelName,
  clip,
  isFocused = false,
  onToggleFocus,
  onOpenCalibration,
}: CameraTileProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isMuted, setIsMuted] = useState(true);
  const [videoError, setVideoError] = useState(false);
  const [resolution, setResolution] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  const toggleNativeFullscreen = () => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      containerRef.current.requestFullscreen().catch(() => {});
    }
  };

  const isPlaying = useCaseStore((s) => s.isPlaying);
  const playbackSpeed = useCaseStore((s) => s.playbackSpeed);
  const masterPlayheadTime = useCaseStore((s) => s.masterPlayheadTime);
  const cameraOffsets = useCaseStore((s) => s.cameraOffsets);

  const offsetSeconds = cameraOffsets[cameraId] || 0;

  // Compute calibrated display time for this camera
  const calibratedDate = React.useMemo(() => {
    try {
      const baseMs = new Date(masterPlayheadTime).getTime();
      if (isNaN(baseMs)) return new Date();
      return new Date(baseMs + offsetSeconds * 1000);
    } catch {
      return new Date();
    }
  }, [masterPlayheadTime, offsetSeconds]);

  // Sync play/pause state
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !clip) return;

    if (isPlaying) {
      v.play().catch(() => {
        // Auto-play policy browser mitigation
      });
    } else {
      v.pause();
    }
  }, [isPlaying, clip]);

  // Sync playback speed
  useEffect(() => {
    const v = videoRef.current;
    if (!v) return;
    v.playbackRate = playbackSpeed;
  }, [playbackSpeed]);

  const handleLoadedMetadata = () => {
    const v = videoRef.current;
    if (v) {
      setResolution(`${v.videoWidth}x${v.videoHeight}`);
      setVideoError(false);
    }
  };

  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
  const streamUrl = clip?.stream_url || (clip?.id ? `${apiBase}/carver/stream/${clip.id}` : null);

  return (
    <div
      ref={containerRef}
      className={`relative rounded-xl bg-card border overflow-hidden flex flex-col justify-between p-2.5 transition-all group h-full w-full ${
        isFullscreen
          ? "fixed inset-0 z-50 rounded-none border-none"
          : isFocused
            ? "border-primary ring-2 ring-primary/30 shadow-2xl z-20"
            : "border-border hover:border-border/80 shadow-md"
      }`}
    >
      {/* Top HUD Header */}
      <div className="flex items-center justify-between z-10 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Badge
            variant={clip ? "default" : "secondary"}
            className="font-mono text-[11px] px-2 py-0.5 font-bold shrink-0 flex items-center gap-1.5"
          >
            {clip && <Radio className="size-2 text-emerald-400 animate-pulse" />}
            CH {cameraId}
          </Badge>

          <span className="text-xs font-semibold truncate text-foreground/90">{channelName}</span>

          {offsetSeconds !== 0 && (
            <Badge
              variant="outline"
              className="text-[10px] font-mono border-amber-500/40 text-amber-400 bg-amber-500/10 cursor-pointer hover:bg-amber-500/20 transition-colors shrink-0"
              onClick={onOpenCalibration}
              title="Camera clock calibrated offset"
            >
              <Clock className="size-2.5 mr-1" />
              {offsetSeconds > 0 ? `+${offsetSeconds}s` : `${offsetSeconds}s`}
            </Badge>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity">
          {clip && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setIsMuted(!isMuted)}
              className="text-muted-foreground hover:text-foreground"
              title={isMuted ? "Unmute Audio" : "Mute Audio"}
            >
              {isMuted ? <VolumeX className="size-3.5" /> : <Volume2 className="size-3.5" />}
            </Button>
          )}

          {onOpenCalibration && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onOpenCalibration}
              className="text-muted-foreground hover:text-foreground"
              title="Calibrate Camera Clock Offset"
            >
              <Clock className="size-3.5" />
            </Button>
          )}

          {onToggleFocus && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={onToggleFocus}
              className="text-muted-foreground hover:text-foreground"
              title={isFocused ? "Restore Grid Layout" : "Maximize Camera Tile"}
            >
              {isFocused ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
            </Button>
          )}

          <Button
            variant="ghost"
            size="icon-xs"
            onClick={toggleNativeFullscreen}
            className="text-muted-foreground hover:text-foreground"
            title={isFullscreen ? "Exit Fullscreen (Esc)" : "Enter Browser Fullscreen"}
          >
            {isFullscreen ? <Shrink className="size-3.5" /> : <Expand className="size-3.5" />}
          </Button>
        </div>
      </div>

      {/* Video Canvas / Video Stream */}
      <div className="absolute inset-0 flex items-center justify-center bg-black overflow-hidden">
        {streamUrl && !videoError ? (
          <video
            ref={videoRef}
            src={streamUrl}
            playsInline
            muted={isMuted}
            preload="auto"
            onLoadedMetadata={handleLoadedMetadata}
            onError={() => setVideoError(true)}
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="text-center space-y-2 select-none p-4">
            {videoError ? (
              <>
                <VideoOff className="size-8 text-destructive/40 mx-auto" />
                <p className="text-xs font-mono text-destructive/70 font-semibold">
                  STREAM PLAYBACK DECODING ERROR
                </p>
                <p className="text-[10px] font-mono text-muted-foreground">
                  Check codec compatibility or carve again.
                </p>
              </>
            ) : (
              <>
                <Camera className="size-8 text-muted-foreground/30 mx-auto" />
                <p className="text-xs font-mono text-muted-foreground/70 font-semibold">
                  CH {cameraId} · STREAM STANDBY
                </p>
                <p className="text-[10px] font-mono text-muted-foreground/50">
                  Awaiting keyframe sync or carved sectors...
                </p>
              </>
            )}
          </div>
        )}
      </div>

      {/* Bottom Forensic HUD Overlay */}
      <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground z-10 bg-background/80 backdrop-blur-md px-2.5 py-1 rounded-md border border-border/50 gap-2">
        <div className="flex items-center gap-2 truncate">
          <span className="text-primary font-semibold">
            {format(calibratedDate, "yyyy-MM-dd hh:mm:ss a")}
          </span>
          {clip?.start_sector !== undefined && (
            <span className="text-muted-foreground/80 hidden sm:inline">
              Sec: 0x{clip.start_sector.toString(16).toUpperCase()}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {resolution && <span className="text-emerald-400 font-semibold">{resolution}</span>}
          {clip?.codec && (
            <span className="bg-secondary px-1.5 py-0.5 rounded text-[9px] text-muted-foreground">
              {clip.codec}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
