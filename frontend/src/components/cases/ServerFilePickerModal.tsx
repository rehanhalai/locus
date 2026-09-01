import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Folder,
  FileCode2,
  FolderUp,
  HardDrive,
  Home,
  Star,
  Search,
  Check,
  X,
  FileQuestion,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ScrollArea } from "../ui/scroll-area";
import { Badge } from "../ui/badge";
import { casesApi } from "../../api/cases";
import type { FsEntry, FsBrowseShortcut } from "../../types/case";

interface ServerFilePickerModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (path: string, size?: string) => void;
  initialPath?: string;
}

export function ServerFilePickerModal({
  open,
  onOpenChange,
  onSelect,
  initialPath,
}: ServerFilePickerModalProps) {
  const [currentPath, setCurrentPath] = useState<string>(initialPath || "");
  const [selectedEntry, setSelectedEntry] = useState<FsEntry | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>("");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["browse-fs", currentPath],
    queryFn: () => casesApi.browseFilesystem(currentPath || undefined),
    enabled: open,
    staleTime: 5000,
  });

  const activePath = data?.current_path || currentPath;
  const parentPath = data?.parent_path;
  const entries = data?.entries || [];
  const shortcuts = data?.shortcuts || [];

  // Filter entries based on search
  const filteredEntries = entries.filter((e) =>
    e.name.toLowerCase().includes(searchFilter.trim().toLowerCase())
  );

  const handleNavigate = (path: string) => {
    setCurrentPath(path);
    setSelectedEntry(null);
    setSearchFilter("");
  };

  const handleConfirmSelection = () => {
    if (selectedEntry && !selectedEntry.is_dir) {
      onSelect(selectedEntry.path, selectedEntry.size);
      onOpenChange(false);
    }
  };

  // Split path for interactive breadcrumb
  const pathSegments = activePath ? activePath.split("/").filter(Boolean) : [];

  const getShortcutIcon = (iconType: string) => {
    switch (iconType) {
      case "workspace":
        return <Star className="size-3.5 text-amber-400 shrink-0" />;
      case "home":
        return <Home className="size-3.5 text-cyan-400 shrink-0" />;
      case "drive":
      case "mount":
      case "root":
        return <HardDrive className="size-3.5 text-primary shrink-0" />;
      default:
        return <Folder className="size-3.5 text-muted-foreground shrink-0" />;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl bg-card border-border p-0 gap-0 overflow-hidden">
        <DialogHeader className="p-4 border-b border-border bg-secondary/30">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="text-sm font-semibold font-heading flex items-center gap-2">
                <Folder className="size-4 text-primary" />
                Workstation File & Evidence Explorer
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Browse directories directly on the forensic workstation to pick raw bitstream disk
                images.
              </DialogDescription>
            </div>
          </div>

          {/* Navigation Bar: Back/Up + Breadcrumbs + Search */}
          <div className="flex items-center gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="xs"
              disabled={!parentPath || isLoading}
              onClick={() => parentPath && handleNavigate(parentPath)}
              className="gap-1 text-xs shrink-0"
              title="Navigate to parent directory"
            >
              <FolderUp className="size-3" />
              Up
            </Button>

            {/* Breadcrumb Path Bar */}
            <div className="flex-1 px-2.5 py-1 rounded-md bg-background border border-border flex items-center gap-1 overflow-x-auto text-xs font-mono scrollbar-none">
              <button
                type="button"
                onClick={() => handleNavigate("/")}
                className="hover:text-primary transition-colors text-muted-foreground"
              >
                /
              </button>
              {pathSegments.map((segment, idx) => {
                const subPath = "/" + pathSegments.slice(0, idx + 1).join("/");
                const isLast = idx === pathSegments.length - 1;
                return (
                  <div key={subPath} className="flex items-center gap-1 shrink-0">
                    <ChevronRight className="size-3 text-muted-foreground/50" />
                    <button
                      type="button"
                      onClick={() => handleNavigate(subPath)}
                      className={`hover:text-primary transition-colors ${
                        isLast ? "font-bold text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {segment}
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Search filter in current directory */}
            <div className="relative w-44 shrink-0">
              <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter files..."
                className="h-7 pl-8 text-xs font-mono"
              />
              {searchFilter && (
                <button
                  type="button"
                  onClick={() => setSearchFilter("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-12 h-95 min-h-95 max-h-95 overflow-hidden">
          {/* Left Sidebar: Shortcuts */}
          <div className="col-span-4 border-r border-border bg-secondary/20 p-3 space-y-3 h-full overflow-y-auto">
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground font-semibold">
              Quick Locations
            </p>
            <div className="space-y-1">
              {shortcuts.map((sc: FsBrowseShortcut) => (
                <button
                  key={sc.path}
                  type="button"
                  onClick={() => handleNavigate(sc.path)}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors flex items-center gap-2 ${
                    activePath === sc.path
                      ? "bg-primary/20 text-primary font-semibold border border-primary/30"
                      : "hover:bg-secondary/60 text-foreground"
                  }`}
                >
                  {getShortcutIcon(sc.icon_type)}
                  <span className="truncate">{sc.name}</span>
                </button>
              ))}
            </div>

            <div className="pt-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground font-semibold">
                Supported Types
              </p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                {[".dd", ".raw", ".img", ".bin", ".iso", ".001", ".e01", ".vmdk", ".dav"].map(
                  (ext) => (
                    <span
                      key={ext}
                      className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-secondary border border-border text-muted-foreground"
                    >
                      {ext}
                    </span>
                  )
                )}
              </div>
            </div>
          </div>

          {/* Right Area: Directory Listing */}
          <div className="col-span-8 p-0 flex flex-col h-full min-h-0 overflow-hidden bg-background">
            <ScrollArea className="h-full w-full p-2">
              {isLoading ? (
                <div className="flex items-center justify-center h-48 text-muted-foreground gap-2 text-xs">
                  <Loader2 className="size-4 animate-spin text-primary" />
                  Reading filesystem...
                </div>
              ) : isError ? (
                <div className="p-4 text-xs text-destructive text-center space-y-2">
                  <p>Failed to access directory: {activePath}</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="xs"
                    onClick={() => refetch()}
                    className="text-xs"
                  >
                    Retry
                  </Button>
                </div>
              ) : filteredEntries.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-muted-foreground text-xs gap-1">
                  <Folder className="size-8 stroke-1 text-muted-foreground/40" />
                  <p>No files or folders found</p>
                </div>
              ) : (
                <div className="space-y-0.5">
                  {filteredEntries.map((entry) => {
                    const isSelected = selectedEntry?.path === entry.path;

                    if (entry.is_dir) {
                      return (
                        <div
                          key={entry.path}
                          onClick={() => handleNavigate(entry.path)}
                          className="px-2.5 py-1.5 rounded-md hover:bg-secondary/70 cursor-pointer flex items-center justify-between text-xs transition-colors group"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <Folder className="size-4 text-amber-400 group-hover:text-amber-300 shrink-0" />
                            <span className="font-mono text-foreground truncate font-medium">
                              {entry.name}
                            </span>
                          </div>
                          <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                            Directory
                          </span>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={entry.path}
                        onClick={() => setSelectedEntry(entry)}
                        onDoubleClick={() => {
                          setSelectedEntry(entry);
                          onSelect(entry.path, entry.size);
                          onOpenChange(false);
                        }}
                        className={`px-2.5 py-1.5 rounded-md cursor-pointer flex items-center justify-between text-xs transition-all ${
                          isSelected
                            ? "bg-primary/20 border border-primary/40 text-foreground"
                            : entry.is_forensic
                              ? "hover:bg-secondary/60 text-foreground bg-secondary/15"
                              : "hover:bg-secondary/40 text-muted-foreground opacity-75"
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          {entry.is_forensic ? (
                            <FileCode2 className="size-4 text-cyan-400 shrink-0" />
                          ) : (
                            <FileQuestion className="size-4 text-muted-foreground shrink-0" />
                          )}
                          <span
                            className={`font-mono truncate ${
                              entry.is_forensic ? "font-semibold text-foreground" : ""
                            }`}
                          >
                            {entry.name}
                          </span>
                          {entry.is_forensic && (
                            <Badge
                              variant="outline"
                              className="text-[9px] px-1 py-0 h-4 bg-cyan-500/10 text-cyan-400 border-cyan-500/20 font-mono"
                            >
                              RAW
                            </Badge>
                          )}
                        </div>

                        <div className="flex items-center gap-3 shrink-0 font-mono text-[11px]">
                          <span className="text-muted-foreground">{entry.size}</span>
                          <span className="text-muted-foreground/60 text-[10px] hidden sm:inline">
                            {entry.modified_at}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-secondary/30 flex items-center justify-between">
          <div className="min-w-0 flex-1 pr-3">
            {selectedEntry ? (
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-muted-foreground shrink-0">Selected:</span>
                <span className="text-primary font-bold truncate">{selectedEntry.name}</span>
                <span className="text-muted-foreground shrink-0">({selectedEntry.size})</span>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground font-mono">
                Click a file to select it, or double-click to confirm immediately.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!selectedEntry || selectedEntry.is_dir}
              onClick={handleConfirmSelection}
              className="gap-1.5 font-semibold"
            >
              <Check className="size-3.5" />
              Select File
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
