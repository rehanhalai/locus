import {
  Camera,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  SlidersHorizontal,
  Maximize2,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { useCaseStore } from "../stores/useCaseStore";

export function InvestigatePage() {
  const isPlaying = useCaseStore((s) => s.isPlaying);
  const togglePlay = useCaseStore((s) => s.togglePlay);
  const stepFrame = useCaseStore((s) => s.stepFrame);
  const masterPlayheadTime = useCaseStore((s) => s.masterPlayheadTime);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* 2x2 Multi-Cam Synchronized Grid */}
      <div className="flex-1 grid grid-cols-2 grid-rows-2 gap-2 p-3 min-h-0">
        {[1, 2, 3, 4].map((camId) => (
          <div
            key={camId}
            className="relative rounded-xl bg-card border border-border overflow-hidden flex flex-col justify-between p-3 group"
          >
            {/* Tile Top Header */}
            <div className="flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded bg-primary/20 text-primary text-xs font-mono font-bold">
                  CH {camId}
                </span>
                <span className="text-xs text-muted-foreground font-medium">
                  {camId === 1
                    ? "Main Entrance"
                    : camId === 2
                      ? "Cash Counter"
                      : camId === 3
                        ? "Vault Area"
                        : "Street Corner"}
                </span>
              </div>

              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button variant="ghost" size="icon-xs" title="Maximize View">
                  <Maximize2 className="size-3.5" />
                </Button>
              </div>
            </div>

            {/* Video Canvas / Placeholder Screen */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <div className="text-center space-y-1">
                <Camera className="size-8 text-muted-foreground/30 mx-auto" />
                <p className="text-xs font-mono text-muted-foreground/70">
                  CAMERA {camId} STREAM SYNCED
                </p>
                <p className="text-[10px] font-mono text-primary/80">
                  {masterPlayheadTime.slice(11, 23)} UTC
                </p>
              </div>
            </div>

            {/* Tile Bottom HUD */}
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground z-10 bg-background/60 backdrop-blur-xs px-2 py-1 rounded-md border border-border/40">
              <span>Sector: 0x00A4000</span>
              <span className="text-emerald-400">1080p @ 25fps</span>
            </div>
          </div>
        ))}
      </div>

      {/* Unified Master Timeline Scrubber Bar */}
      <div className="h-20 border-t border-border bg-card/80 backdrop-blur-md px-6 flex flex-col justify-center space-y-2 select-none">
        {/* Playhead Slider Track */}
        <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
          <span>14:00:00 UTC</span>
          <div className="flex-1 relative h-6 bg-secondary/80 rounded-md border border-border flex items-center px-2 cursor-pointer">
            <div className="w-1/3 h-2 bg-primary/40 rounded-sm relative">
              <div className="absolute right-0 top-1/2 -translate-y-1/2 size-4 bg-primary rounded-full shadow-md shadow-primary/40 border-2 border-background" />
            </div>
          </div>
          <span>15:00:00 UTC</span>
        </div>

        {/* Transport Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="xs"
              onClick={() => stepFrame(-1)}
              title="Step Back 1 Frame [Hotkey: []"
            >
              <SkipBack className="size-3 mr-1" />1 Frame
            </Button>

            <Button
              variant={isPlaying ? "destructive" : "default"}
              size="sm"
              onClick={togglePlay}
              className="gap-1.5 px-4 font-semibold"
              title="Play/Pause [Hotkey: Space]"
            >
              {isPlaying ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
              {isPlaying ? "Pause" : "Play"}
            </Button>

            <Button
              variant="outline"
              size="xs"
              onClick={() => stepFrame(1)}
              title="Step Forward 1 Frame [Hotkey: ]]"
            >
              1 Frame
              <SkipForward className="size-3 ml-1" />
            </Button>
          </div>

          {/* Center Timecode Display */}
          <div className="text-sm font-mono font-bold tracking-wider text-primary">
            {masterPlayheadTime.slice(11, 23)} UTC
          </div>

          {/* Right Tools */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted-foreground">Speed: 1.0x</span>
            <Button variant="ghost" size="xs">
              <SlidersHorizontal className="size-3.5 mr-1" />
              Calibrate Offsets
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
