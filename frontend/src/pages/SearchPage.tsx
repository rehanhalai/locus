import { useState } from "react";
import { Search, Filter, Play, Tag, Sparkles } from "lucide-react";
import { Button } from "../components/ui/button";
import { useNavigate } from "react-router-dom";
import { useCaseStore } from "../stores/useCaseStore";

export function SearchPage() {
  const navigate = useNavigate();
  const setMasterPlayheadTime = useCaseStore((s) => s.setMasterPlayheadTime);
  const setIsPlaying = useCaseStore((s) => s.setIsPlaying);

  const [filterPerson, setFilterPerson] = useState(true);
  const [filterVehicle, setFilterVehicle] = useState(false);
  const [filterBag, setFilterBag] = useState(false);

  // Mock detection events for UI skeleton
  const events = [
    {
      id: "ev-1",
      camera_id: 2,
      camera_name: "Cam 2 (Counter)",
      timestamp: "2026-08-30T14:02:15.000Z",
      display_time: "14:02:15 UTC",
      label: "Person",
      confidence: 94.2,
      bbox: "[0.12, 0.45, 0.88, 0.72]",
    },
    {
      id: "ev-2",
      camera_id: 1,
      camera_name: "Cam 1 (Entrance)",
      timestamp: "2026-08-30T14:03:40.000Z",
      display_time: "14:03:40 UTC",
      label: "Person",
      confidence: 91.8,
      bbox: "[0.10, 0.32, 0.85, 0.65]",
    },
    {
      id: "ev-3",
      camera_id: 4,
      camera_name: "Cam 4 (Street)",
      timestamp: "2026-08-30T14:07:22.000Z",
      display_time: "14:07:22 UTC",
      label: "Black Sedan",
      confidence: 89.5,
      bbox: "[0.40, 0.15, 0.78, 0.90]",
    },
  ];

  const handleJumpToPlay = (isoTimestamp: string) => {
    // Cross-Room Deep Linking: set master playhead time, start playback, and switch to Room 1
    setMasterPlayheadTime(isoTimestamp);
    setIsPlaying(true);
    navigate("/investigate");
  };

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {/* Left Filter Bar */}
      <div className="w-72 border-r border-border bg-card/40 p-5 space-y-6 flex-shrink-0">
        <div>
          <h2 className="text-sm font-semibold font-heading flex items-center gap-2">
            <Filter className="size-4 text-primary" />
            Detection Filters
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Filter indexed YOLOv8 detections by object class and camera.
          </p>
        </div>

        {/* Category Checkboxes */}
        <div className="space-y-2.5">
          <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Target Classes
          </label>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={filterPerson}
                onChange={(e) => setFilterPerson(e.target.checked)}
                className="rounded border-border text-primary focus:ring-primary size-3.5"
              />
              <span>Persons / Suspects</span>
            </label>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={filterVehicle}
                onChange={(e) => setFilterVehicle(e.target.checked)}
                className="rounded border-border text-primary focus:ring-primary size-3.5"
              />
              <span>Vehicles (Cars / Vans)</span>
            </label>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={filterBag}
                onChange={(e) => setFilterBag(e.target.checked)}
                className="rounded border-border text-primary focus:ring-primary size-3.5"
              />
              <span>Bags / Backpacks</span>
            </label>
          </div>
        </div>

        {/* Confidence Threshold */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-muted-foreground">Min Confidence</span>
            <span className="text-primary font-bold">85%</span>
          </div>
          <input
            type="range"
            min="50"
            max="99"
            defaultValue="85"
            className="w-full accent-primary h-1.5 bg-secondary rounded-lg"
          />
        </div>

        {/* Camera Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Camera Channel
          </label>
          <select className="w-full bg-secondary border border-border text-xs rounded-lg px-2.5 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary">
            <option value="all">All Cameras (1-4)</option>
            <option value="1">Channel 1 (Main Entrance)</option>
            <option value="2">Channel 2 (Cash Counter)</option>
            <option value="3">Channel 3 (Vault Area)</option>
            <option value="4">Channel 4 (Street Corner)</option>
          </select>
        </div>

        <Button size="sm" className="w-full gap-2">
          <Sparkles className="size-3.5" />
          Apply Filters
        </Button>
      </div>

      {/* Right Events Grid */}
      <div className="flex-1 p-6 overflow-y-auto space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-base font-semibold font-heading flex items-center gap-2">
            <Search className="size-4 text-primary" />
            Indexed AI Event Matches
            <span className="text-xs font-mono font-normal bg-secondary px-2 py-0.5 rounded text-muted-foreground">
              {events.length} Results
            </span>
          </h1>
        </div>

        {/* Grid of Thumbnail Cards matching Excalidraw design */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {events.map((ev) => (
            <div
              key={ev.id}
              className="p-4 rounded-xl bg-card border border-border hover:border-primary/50 transition-all space-y-3 group"
            >
              {/* Thumbnail Container */}
              <div className="h-36 rounded-lg bg-black/60 border border-border/50 relative overflow-hidden flex items-center justify-center">
                <div className="text-center space-y-1">
                  <Tag className="size-6 text-muted-foreground/30 mx-auto" />
                  <span className="text-[10px] font-mono text-muted-foreground/60">
                    BBox: {ev.bbox}
                  </span>
                </div>

                <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 text-violet-400 text-[11px] font-mono font-bold border border-violet-500/30">
                  🎯 {ev.label} ({ev.confidence}%)
                </div>
              </div>

              {/* Event Metadata */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono text-primary font-semibold">🕒 {ev.display_time}</span>
                  <span className="font-mono text-muted-foreground text-[11px]">
                    📷 {ev.camera_name}
                  </span>
                </div>
              </div>

              {/* Cross-Room Jump Button */}
              <Button
                size="sm"
                className="w-full gap-2 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground border border-primary/20"
                onClick={() => handleJumpToPlay(ev.timestamp)}
              >
                <Play className="size-3.5 fill-current" />
                Jump to Play ▶
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
