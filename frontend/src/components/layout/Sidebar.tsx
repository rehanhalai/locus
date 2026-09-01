import { useLocation, useNavigate } from "react-router-dom";
import {
  Compass,
  FolderLock,
  Camera,
  Search,
  Scale,
  ScrollText,
  User,
  Settings,
} from "lucide-react";
import type { ElementType } from "react";
import { useCaseStore } from "../../stores/useCaseStore";
import { cn } from "../../lib/utils";

interface NavItem {
  id: string;
  name: string;
  path: string;
  icon: ElementType;
  hotkey: string;
  roomNumber: number;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "investigate",
    name: "Multi-Cam Grid & Player",
    path: "/investigate",
    icon: Camera,
    hotkey: "1",
    roomNumber: 1,
  },
  {
    id: "search",
    name: "AI Intelligence & Search",
    path: "/search",
    icon: Search,
    hotkey: "2",
    roomNumber: 2,
  },
  {
    id: "export",
    name: "Evidence Export & Hashing",
    path: "/export",
    icon: Scale,
    hotkey: "3",
    roomNumber: 3,
  },
  {
    id: "audit",
    name: "Audit Trail Ledger",
    path: "/audit",
    icon: ScrollText,
    hotkey: "4",
    roomNumber: 4,
  },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeCaseId = useCaseStore((s) => s.activeCaseId);
  const investigatorName = useCaseStore((s) => s.investigatorName);

  return (
    <aside className="w-16 flex-shrink-0 bg-sidebar border-r border-sidebar-border flex flex-col items-center justify-between py-4 select-none z-30">
      {/* Top Section: Logo + Case Hub */}
      <div className="flex flex-col items-center gap-6 w-full">
        {/* Locus Brand Icon */}
        <button
          onClick={() => navigate("/cases")}
          className="group relative flex items-center justify-center size-10 rounded-xl bg-primary/10 hover:bg-primary/20 text-primary transition-all duration-200"
          title="LOCUS Forensic Workstation"
        >
          <Compass className="size-5 transition-transform duration-300 group-hover:rotate-45" />
          <span className="sr-only">Locus Home</span>
        </button>

        {/* Case Hub Selector */}
        <button
          onClick={() => navigate("/cases")}
          className={cn(
            "group relative flex items-center justify-center size-10 rounded-xl transition-all duration-200",
            location.pathname === "/cases"
              ? "bg-secondary text-foreground ring-1 ring-border shadow-sm"
              : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
          )}
          title="Cases Hub [Hotkey: 0]"
        >
          <FolderLock className="size-5" />
          <span className="absolute -top-1 -right-1 text-[9px] font-mono font-bold bg-muted px-1 rounded-sm text-muted-foreground">
            0
          </span>
        </button>

        {/* Separator */}
        <div className="w-8 h-px bg-border my-1" />

        {/* 4 Core Rooms Navigation */}
        <nav className="flex flex-col items-center gap-3 w-full px-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            const isDisabled = !activeCaseId && item.path !== "/cases";

            return (
              <button
                key={item.id}
                onClick={() => !isDisabled && navigate(item.path)}
                disabled={isDisabled}
                className={cn(
                  "group relative flex items-center justify-center size-10 rounded-xl transition-all duration-200",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                    : isDisabled
                      ? "opacity-30 cursor-not-allowed text-muted-foreground"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
                title={`${item.name} [Hotkey: ${item.hotkey}]`}
              >
                <Icon className="size-5" />
                <span
                  className={cn(
                    "absolute -top-1 -right-1 text-[9px] font-mono font-bold px-1 rounded-sm",
                    isActive
                      ? "bg-primary-foreground text-primary"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {item.hotkey}
                </span>

                {/* Floating tooltip label */}
                <div className="absolute left-16 px-2.5 py-1.5 rounded-lg bg-popover text-popover-foreground text-xs font-medium whitespace-nowrap shadow-lg border border-border opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-150 z-50">
                  <div className="flex items-center gap-2">
                    <span>{item.name}</span>
                    <kbd className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded border border-border text-muted-foreground">
                      [{item.hotkey}]
                    </kbd>
                  </div>
                </div>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Section: Profile & Settings */}
      <div className="flex flex-col items-center gap-3 w-full">
        <button
          className="group relative flex items-center justify-center size-10 rounded-xl text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
          title={`Investigator: ${investigatorName}`}
        >
          <div className="size-8 rounded-full bg-secondary flex items-center justify-center text-xs font-medium text-secondary-foreground border border-border">
            <User className="size-4" />
          </div>
        </button>

        <button
          className="flex items-center justify-center size-9 rounded-xl text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
          title="Settings"
        >
          <Settings className="size-4" />
        </button>
      </div>
    </aside>
  );
}
