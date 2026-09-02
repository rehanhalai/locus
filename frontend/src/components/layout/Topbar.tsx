import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FolderOpen, Activity, AlertCircle, Clock, ChevronDown } from "lucide-react";
import { SidebarTrigger } from "../ui/sidebar";
import { useCaseStore } from "../../stores/useCaseStore";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { format } from "date-fns";

export function Topbar() {
  const navigate = useNavigate();
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const runningTasks = useCaseStore((s) => s.runningTasks);
  const toggleTaskDrawer = useCaseStore((s) => s.toggleTaskDrawer);

  const { data: healthData } = useQuery({
    queryKey: ["backend-health"],
    queryFn: () => api.checkHealth(),
    refetchInterval: 10000,
    staleTime: 5000,
  });

  const backendOnline = healthData?.status === "online";

  const [utcTime, setUtcTime] = useState<string>("");

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setUtcTime(format(now, "yyyy-MM-dd hh:mm:ss a"));
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);
    return () => clearInterval(timer);
  }, []);

  const activeJobs = runningTasks.filter(
    (t) => t.status === "PROCESSING" || t.status === "PENDING"
  );
  const avgProgress =
    activeJobs.length > 0
      ? Math.round(activeJobs.reduce((acc, t) => acc + t.progress_percent, 0) / activeJobs.length)
      : 0;

  return (
    <header className="h-12 border-b border-border bg-card/60 backdrop-blur-md px-3 flex items-center justify-between select-none z-20">
      {/* Left: Sidebar Trigger & Active Case Pill */}
      <div className="flex items-center gap-2">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
        <div className="h-4 w-px bg-border mx-1" />

        {activeCaseId ? (
          <button
            onClick={() => navigate("/cases")}
            className="flex items-center gap-2 px-3 py-1 rounded-lg bg-secondary/80 hover:bg-secondary border border-border text-sm font-medium transition-colors"
          >
            <FolderOpen className="size-4 text-primary" />
            <span className="font-mono text-xs font-semibold text-primary">
              {activeCaseNumber || "CASE-ACTIVE"}
            </span>
            {activeCaseName && (
              <span className="text-muted-foreground text-xs max-w-[200px] truncate">
                · {activeCaseName}
              </span>
            )}
            <ChevronDown className="size-3 text-muted-foreground ml-1" />
          </button>
        ) : (
          <button
            onClick={() => navigate("/cases")}
            className="flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium hover:bg-amber-500/20 transition-colors"
          >
            <AlertCircle className="size-3.5" />
            <span>No Active Case Selected — Open Cases Hub</span>
          </button>
        )}
      </div>

      {/* Center: Live UTC Master Clock */}
      <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-muted/30 border border-border/50 text-xs font-mono text-muted-foreground">
        <Clock className="size-3.5 text-primary animate-pulse" />
        <span>{utcTime || "SYNCING MASTER CLOCK..."}</span>
      </div>

      {/* Right: Background Tasks & Engine Status */}
      <div className="flex items-center gap-3">
        {/* Background Task Pill */}
        {activeJobs.length > 0 ? (
          <button
            onClick={toggleTaskDrawer}
            className="flex items-center gap-2 px-3 py-1 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-400 text-xs font-mono transition-all animate-pulse"
            title="Click to view background task progress"
          >
            <Activity className="size-3.5 animate-spin" />
            <span>
              {activeJobs.length} Job{activeJobs.length > 1 ? "s" : ""} ({avgProgress}%)
            </span>
          </button>
        ) : (
          <button
            onClick={toggleTaskDrawer}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-muted-foreground hover:bg-muted/40 text-xs transition-colors"
            title="No active background tasks (Press T to open drawer)"
          >
            <Activity className="size-3.5 text-muted-foreground" />
            <span className="text-[11px]">Tasks</span>
          </button>
        )}

        {/* Engine Live Status Indicator */}
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-muted/30 border border-border/40 text-xs"
          title={backendOnline ? "Forensic Engine is Online" : "Cannot reach backend engine"}
        >
          {backendOnline ? (
            <>
              <span className="size-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
              <span className="text-[11px] font-mono text-emerald-400">Engine Live</span>
            </>
          ) : (
            <>
              <span className="size-2 rounded-full bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.6)] animate-ping" />
              <span className="text-[11px] font-mono text-destructive">Engine Offline</span>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
