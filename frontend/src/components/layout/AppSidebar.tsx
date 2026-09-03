import { useLocation, useNavigate } from "react-router-dom";
import {
  Compass,
  FolderLock,
  Camera,
  Search,
  Scale,
  ScrollText,
  User,
  Shield,
  FolderOpen,
  ArrowRightLeft,
} from "lucide-react";
import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarMenuBadge,
  SidebarRail,
  useSidebar,
} from "../ui/sidebar";
import { useCaseStore } from "../../stores/useCaseStore";

interface NavRoom {
  id: string;
  name: string;
  roomLabel: string;
  path: string;
  icon: typeof Camera;
  hotkey: string;
  roomNumber: number;
}

const ROOM_ITEMS: NavRoom[] = [
  {
    id: "investigate",
    name: "Multi-Cam Grid",
    roomLabel: "Room 1",
    path: "/investigate",
    icon: Camera,
    hotkey: "1",
    roomNumber: 1,
  },
  {
    id: "search",
    name: "AI Intelligence",
    roomLabel: "Room 2",
    path: "/search",
    icon: Search,
    hotkey: "2",
    roomNumber: 2,
  },
  {
    id: "export",
    name: "Export & Hashing",
    roomLabel: "Room 3",
    path: "/export",
    icon: Scale,
    hotkey: "3",
    roomNumber: 3,
  },
  {
    id: "audit",
    name: "Audit Trail",
    roomLabel: "Room 4",
    path: "/audit",
    icon: ScrollText,
    hotkey: "4",
    roomNumber: 4,
  },
];

export function AppSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";

  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const activeCaseNumber = useCaseStore((s) => s.activeCaseNumber);
  const activeCaseName = useCaseStore((s) => s.activeCaseName);
  const investigatorName = useCaseStore((s) => s.investigatorName);
  const activeEvidenceId = useCaseStore((s) => s.activeEvidenceId);

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border select-none">
      {/* Brand Header */}
      <SidebarHeader className="border-b border-sidebar-border/60 py-3">
        <div
          onClick={() => navigate("/cases")}
          className="flex items-center gap-3 px-2 cursor-pointer group"
          title="LOCUS Forensic Workstation"
        >
          <div className="size-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary group-hover:bg-primary/20 transition-colors shrink-0">
            <Compass className="size-5 transition-transform duration-300 group-hover:rotate-45" />
          </div>

          {!isCollapsed && (
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="font-heading font-black tracking-wider text-foreground text-sm">
                  LOCUS
                </span>
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-primary/15 text-primary border border-primary/25">
                  DVR
                </span>
              </div>
              <span className="text-[10px] text-muted-foreground font-mono truncate">
                Forensic Workstation
              </span>
            </div>
          )}
        </div>
      </SidebarHeader>

      {/* Main Navigation Content */}
      <SidebarContent>
        {/* Workspace Hub */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Workspace
          </SidebarGroupLabel>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                isActive={location.pathname === "/cases"}
                onClick={() => navigate("/cases")}
                tooltip="Cases Hub [Hotkey: 0]"
                className="gap-2.5 font-medium"
              >
                <FolderLock className="size-4 shrink-0 text-primary" />
                <span>Cases Hub</span>
              </SidebarMenuButton>
              <SidebarMenuBadge className="font-mono text-[10px] font-semibold">0</SidebarMenuBadge>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroup>

        {/* 4 Core Forensic Rooms */}
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Forensic Rooms
          </SidebarGroupLabel>
          <SidebarMenu>
            {ROOM_ITEMS.map((room) => {
              const Icon = room.icon;
              const isActive = location.pathname === room.path;
              const isDisabled = !activeCaseId && room.path !== "/cases";

              return (
                <SidebarMenuItem key={room.id}>
                  <SidebarMenuButton
                    isActive={isActive}
                    disabled={isDisabled}
                    onClick={() => !isDisabled && navigate(room.path)}
                    tooltip={`${room.roomLabel}: ${room.name} [${room.hotkey}]`}
                    className={`gap-2.5 ${isDisabled ? "opacity-40 cursor-not-allowed" : ""}`}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="truncate">{room.name}</span>
                  </SidebarMenuButton>
                  <SidebarMenuBadge className="font-mono text-[10px] font-semibold">
                    {room.hotkey}
                  </SidebarMenuBadge>
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>

        {/* Active Case Mini Dossier (Visible in expanded view) */}
        {!isCollapsed && activeCaseId && (
          <SidebarGroup className="mt-auto pb-2">
            <SidebarGroupLabel className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground flex items-center justify-between">
              <span>Active Dossier</span>
              <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            </SidebarGroupLabel>

            <div className="mx-2 p-2.5 rounded-xl bg-sidebar-accent/50 border border-sidebar-border/80 space-y-2">
              <div className="flex items-center gap-2">
                <FolderOpen className="size-4 text-primary shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-mono font-bold text-foreground truncate">
                    {activeCaseNumber || "ACTIVE"}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {activeCaseName || "Ongoing Dossier"}
                  </p>
                </div>
              </div>

              <div className="pt-1 flex items-center justify-between border-t border-sidebar-border/60 text-[10px] font-mono text-muted-foreground">
                <span>{activeEvidenceId ? "Evidence Mounted" : "No Evidence"}</span>
                <button
                  type="button"
                  onClick={() => navigate("/cases")}
                  className="text-primary hover:underline flex items-center gap-1 font-sans font-medium"
                >
                  <ArrowRightLeft className="size-2.5" />
                  Switch
                </button>
              </div>
            </div>
          </SidebarGroup>
        )}
      </SidebarContent>

      {/* Footer: Investigator Profile */}
      <SidebarFooter className="border-t border-sidebar-border/60 py-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip={`Lead Investigator: ${investigatorName}`}
              className="gap-2.5"
            >
              <div className="size-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                <User className="size-4" />
              </div>
              <div className="flex flex-col min-w-0 text-left">
                <span className="text-xs font-medium text-foreground truncate">
                  {investigatorName || "Forensic Examiner"}
                </span>
                <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-1">
                  <Shield className="size-2.5 text-emerald-400" />
                  Authorized Officer
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      {/* Resize / Collapse Rail */}
      <SidebarRail />
    </Sidebar>
  );
}
