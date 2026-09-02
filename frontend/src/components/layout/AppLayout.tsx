import { Outlet } from "react-router-dom";
import { SidebarProvider, SidebarInset } from "../ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { Topbar } from "./Topbar";
import { TaskDrawer } from "./TaskDrawer";
import { GlobalTaskWatcher } from "./GlobalTaskWatcher";
import { useHotkeys } from "../../hooks/useHotkeys";

export function AppLayout() {
  // Bind global forensic keyboard shortcuts (1-4, Space, [, ], T)
  useHotkeys();

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground select-none">
        {/* Collapsible Shadcn Forensic Sidebar */}
        <AppSidebar />

        {/* Main Content Column */}
        <SidebarInset className="flex flex-col flex-1 min-w-0 h-full overflow-hidden bg-background">
          {/* Topbar with Sidebar Trigger, Master Clock & Case Badge */}
          <Topbar />

          {/* Dynamic Route Canvas (Rooms 1-4 or Cases Hub) */}
          <main className="flex-1 min-w-0 overflow-y-auto relative bg-background/50">
            <Outlet />
          </main>
        </SidebarInset>

        {/* Slide-over Background Pipeline Tracker */}
        <TaskDrawer />

        {/* Persistent Floating Task HUD across Page Refreshes */}
        <GlobalTaskWatcher />
      </div>
    </SidebarProvider>
  );
}
