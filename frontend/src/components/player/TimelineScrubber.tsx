import React, { useRef, useState, useCallback, useEffect } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  FastForward,
  RotateCcw,
} from "lucide-react";
import { Button } from "../ui/button";
import { useCaseStore } from "../../stores/useCaseStore";
import type { CarvedClip } from "../../types/video";
import { format } from "date-fns";

interface TimelineScrubberProps {
  clips?: CarvedClip[];
  onOpenCalibration?: () => void;
}

const SPEED_OPTIONS = [0.25, 0.5, 1, 2, 4, 8, 16];

export function TimelineScrubber({ clips = [], onOpenCalibration }: TimelineScrubberProps) {
  const trackRef = useRef<HTMLDivElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [hoverTime, setHoverTime] = useState<Date | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const masterPlayheadTime = useCaseStore((s) => s.masterPlayheadTime);
  const setMasterPlayheadTime = useCaseStore((s) => s.setMasterPlayheadTime);
  const isPlaying = useCaseStore((s) => s.isPlaying);
  const togglePlay = useCaseStore((s) => s.togglePlay);
  const stepFrame = useCaseStore((s) => s.stepFrame);
  const playbackSpeed = useCaseStore((s) => s.playbackSpeed);
  const setPlaybackSpeed = useCaseStore((s) => s.setPlaybackSpeed);
  const timelineStart = useCaseStore((s) => s.timelineStart);
  const timelineEnd = useCaseStore((s) => s.timelineEnd);

  // Compute timeline start and end from carved clips or default window from store
  const { timelineStartMs, timelineEndMs } = React.useMemo(() => {
    if (clips.length > 0) {
      const times = clips.flatMap((c) => [
        new Date(c.start_time).getTime(),
        new Date(c.end_time).getTime(),
      ]);
      const validTimes = times.filter((t) => !isNaN(t));
      if (validTimes.length > 0) {
        const minT = Math.min(...validTimes);
        const maxT = Math.max(...validTimes);
        const buffer = Math.max(30000, (maxT - minT) * 0.05); // 5% buffer
        return {
          timelineStartMs: minT - buffer,
          timelineEndMs: maxT + buffer,
        };
      }
    }
    const sMs = new Date(timelineStart).getTime();
    const eMs = new Date(timelineEnd).getTime();
    return {
      timelineStartMs: isNaN(sMs) ? 0 : sMs,
      timelineEndMs: isNaN(eMs) ? 3600000 : eMs,
    };
  }, [clips, timelineStart, timelineEnd]);

  const totalDurationMs = Math.max(1000, timelineEndMs - timelineStartMs);
  const currentMs = new Date(masterPlayheadTime).getTime() || timelineStartMs;
  const progressPercent = Math.min(
    100,
    Math.max(0, ((currentMs - timelineStartMs) / totalDurationMs) * 100)
  );

  // Playhead animation loop when playing
  useEffect(() => {
    if (!isPlaying) return;

    let lastTick = performance.now();
    let animId: number;

    const tick = (now: number) => {
      const deltaRealMs = now - lastTick;
      lastTick = now;

      const deltaPlayheadMs = deltaRealMs * playbackSpeed;
      const currentPlayhead = new Date(useCaseStore.getState().masterPlayheadTime).getTime();
      let nextMs = currentPlayhead + deltaPlayheadMs;

      // Loop or stop if reaching end of timeline
      if (nextMs >= timelineEndMs) {
        nextMs = timelineStartMs;
      }

      setMasterPlayheadTime(new Date(nextMs).toISOString());
      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, playbackSpeed, timelineStartMs, timelineEndMs, setMasterPlayheadTime]);

  // Handle Seek calculation from pointer position
  const seekToPosition = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return;

      const rect = track.getBoundingClientRect();
      const clickX = Math.max(0, Math.min(rect.width, clientX - rect.left));
      const ratio = clickX / rect.width;
      const seekMs = timelineStartMs + ratio * totalDurationMs;

      setMasterPlayheadTime(new Date(seekMs).toISOString());
    },
    [timelineStartMs, totalDurationMs, setMasterPlayheadTime]
  );

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
    seekToPosition(e.clientX);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      seekToPosition(moveEvent.clientX);
    };

    const handlePointerUp = () => {
      setIsDragging(false);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  };

  const handleTrackMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const track = trackRef.current;
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const ratio = x / rect.width;
    const hoverMs = timelineStartMs + ratio * totalDurationMs;
    setHoverTime(new Date(hoverMs));
    setHoverX(x);
  };

  const handleTrackMouseLeave = () => {
    setHoverTime(null);
    setHoverX(null);
  };

  return (
    <div className="h-24 border-t border-border bg-card/90 backdrop-blur-md px-6 py-2.5 flex flex-col justify-between select-none shrink-0 shadow-lg">
      {/* 1. Timeline Scrubber Track */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
          <span>{format(new Date(timelineStartMs), "yyyy-MM-dd hh:mm:ss a")}</span>

          <div className="flex items-center gap-2">
            <span className="text-primary font-bold">
              {format(new Date(currentMs), "yyyy-MM-dd hh:mm:ss.SSS a")}
            </span>
          </div>

          <span>{format(new Date(timelineEndMs), "yyyy-MM-dd hh:mm:ss a")}</span>
        </div>

        {/* Interactive Scrub Track */}
        <div
          ref={trackRef}
          onPointerDown={handlePointerDown}
          onMouseMove={handleTrackMouseMove}
          onMouseLeave={handleTrackMouseLeave}
          className="relative h-7 bg-secondary/80 rounded-lg border border-border/80 flex items-center px-1 cursor-pointer overflow-hidden group/track"
        >
          {/* Clip Presence Bands */}
          {clips.map((clip) => {
            const cStart = new Date(clip.start_time).getTime();
            const cEnd = new Date(clip.end_time).getTime();
            if (isNaN(cStart) || isNaN(cEnd)) return null;

            const leftPct = Math.max(0, ((cStart - timelineStartMs) / totalDurationMs) * 100);
            const widthPct = Math.min(100 - leftPct, ((cEnd - cStart) / totalDurationMs) * 100);

            return (
              <div
                key={clip.id}
                style={{ left: `${leftPct}%`, width: `${Math.max(0.5, widthPct)}%` }}
                className="absolute top-1 bottom-1 bg-emerald-500/30 border-x border-emerald-500/50 rounded-xs pointer-events-none"
                title={`Cam ${clip.camera_id}: ${clip.start_time} - ${clip.end_time}`}
              />
            );
          })}

          {/* Hover Scrub Indicator */}
          {hoverX !== null && hoverTime && (
            <div
              style={{ left: `${hoverX}px` }}
              className="absolute top-0 bottom-0 w-[1px] bg-foreground/40 pointer-events-none z-10"
            >
              <div className="absolute -top-7 -translate-x-1/2 bg-popover border border-border px-1.5 py-0.5 rounded text-[10px] font-mono shadow-md text-foreground whitespace-nowrap">
                {format(hoverTime, "hh:mm:ss a")}
              </div>
            </div>
          )}

          {/* Played Progress Track */}
          <div
            style={{ width: `${progressPercent}%` }}
            className="h-2 bg-primary/40 rounded-xs transition-all relative pointer-events-none"
          >
            {/* Playhead Needle Handle */}
            <div
              className={`absolute right-0 top-1/2 -translate-y-1/2 size-4.5 bg-primary rounded-full shadow-md shadow-primary/50 border-2 border-background flex items-center justify-center transition-transform ${
                isDragging ? "scale-125 ring-2 ring-primary/40" : "group-hover/track:scale-110"
              }`}
            >
              <div className="size-1.5 bg-background rounded-full" />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Master Transport Bar Controls */}
      <div className="flex items-center justify-between pt-1">
        {/* Left: Play/Pause, Step Frames, Reset */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="xs"
            onClick={() => setMasterPlayheadTime(new Date(timelineStartMs).toISOString())}
            title="Jump to Timeline Start"
          >
            <RotateCcw className="size-3" />
          </Button>

          <Button
            variant="outline"
            size="xs"
            onClick={() => stepFrame(-1)}
            title="Step Back 1 Frame [Hotkey: []"
            className="gap-1 font-mono text-[11px]"
          >
            <SkipBack className="size-3" />1 Fr
          </Button>

          <Button
            variant={isPlaying ? "destructive" : "default"}
            size="sm"
            onClick={togglePlay}
            className="gap-1.5 px-4 font-semibold shadow-xs"
            title="Play/Pause [Hotkey: Space]"
          >
            {isPlaying ? (
              <Pause className="size-3.5" />
            ) : (
              <Play className="size-3.5 fill-current" />
            )}
            <span>{isPlaying ? "Pause" : "Play"}</span>
          </Button>

          <Button
            variant="outline"
            size="xs"
            onClick={() => stepFrame(1)}
            title="Step Forward 1 Frame [Hotkey: ]]"
            className="gap-1 font-mono text-[11px]"
          >
            1 Fr
            <SkipForward className="size-3" />
          </Button>
        </div>

        {/* Center: Large Timecode Readout */}
        <div className="text-center font-mono">
          <span className="text-sm font-bold tracking-wider text-primary">
            {format(new Date(currentMs), "hh:mm:ss.SSS a")}
          </span>
          <span className="text-[10px] text-muted-foreground ml-1.5 font-normal">UTC</span>
        </div>

        {/* Right: Speed Multiplier & Offset Calibration */}
        <div className="flex items-center gap-3">
          {/* Speed Pills */}
          <div className="flex items-center gap-0.5 bg-secondary/80 p-0.5 rounded-lg border border-border">
            <FastForward className="size-3 text-muted-foreground ml-1 mr-0.5 hidden sm:block" />
            {SPEED_OPTIONS.map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaybackSpeed(spd)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono transition-all ${
                  playbackSpeed === spd
                    ? "bg-primary text-primary-foreground font-bold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                title={`Playback Speed: ${spd}x`}
              >
                {spd}x
              </button>
            ))}
          </div>

          {onOpenCalibration && (
            <Button
              variant="outline"
              size="xs"
              onClick={onOpenCalibration}
              className="gap-1.5 text-xs"
            >
              <SlidersHorizontal className="size-3.5 text-primary" />
              <span className="hidden sm:inline">Calibrate Offsets</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
