import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { TaskDrawer } from "./TaskDrawer";
import { useHotkeys } from "../../hooks/useHotkeys";

export function AppLayout() {
  // Bind global forensic keyboard shortcuts (1-4, Space, [, ], T)
  useHotkeys();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground select-none">
      {/* 64px Command Rail Sidebar */}
      <Sidebar />

      {/* Main Content Column */}
      <div className="flex flex-col flex-1 min-w-0 h-full overflow-hidden">
        {/* Topbar with Master Clock & Case Badge */}
        <Topbar />

        {/* Dynamic Route Canvas (Rooms 1-4 or Cases Hub) */}
        <main className="flex-1 min-w-0 overflow-y-auto relative bg-background/50">
          <Outlet />
        </main>
      </div>

      {/* Slide-over Background Pipeline Tracker */}
      <TaskDrawer />
    </div>
  );
}
