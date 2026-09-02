import { useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  HardDrive,
  FileCode2,
  Lock,
  Activity,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  FolderSearch,
  RefreshCcw,
  Usb,
  Cpu,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/tabs";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  SelectGroup,
  SelectLabel,
} from "../ui/select";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Progress } from "../ui/progress";
import { casesApi } from "../../api/cases";
import { useTaskSSE } from "../../hooks/useSSE";
import { useCaseStore } from "../../stores/useCaseStore";
import { useNavigate } from "react-router-dom";
import { ServerFilePickerModal } from "./ServerFilePickerModal";

const ALLOWED_EXTENSIONS = [
  ".dd",
  ".raw",
  ".img",
  ".bin",
  ".iso",
  ".001",
  ".dav",
  ".mp4",
  ".h264",
  ".e01",
  ".e02",
  ".ewf",
  "ewf1",
];

interface EvidenceIntakeModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseId: string;
  caseNumber: string;
}

interface SSEAcquisitionEvent {
  stage?: string;
  status?: string;
  type?: string;
  exit_code?: number;
  percentage?: number;
  progress_percent?: number;
  speed_mbps?: number;
  speed_mb_s?: number;
  rate_mb_s?: number;
  bytes_processed?: number;
  total_bytes?: number;
  sha256?: string;
  md5?: string;
  evidence_id?: string;
  message?: string;
  error?: string;
  device_brand?: string;
}

export function EvidenceIntakeModal({
  open,
  onOpenChange,
  caseId,
  caseNumber,
}: EvidenceIntakeModalProps) {
  const navigate = useNavigate();
  const investigatorName = useCaseStore((s) => s.investigatorName);
  const setActiveEvidenceId = useCaseStore((s) => s.setActiveEvidenceId);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<string>("image");
  const [filePath, setFilePath] = useState<string>("");
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileSize, setSelectedFileSize] = useState<string | null>(null);
  const [explorerOpen, setExplorerOpen] = useState<boolean>(false);

  const [sourceDevice, setSourceDevice] = useState<string>("");
  const [customDevice, setCustomDevice] = useState<string>("");
  const [imageFilename, setImageFilename] = useState<string>("");

  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [sha256Hash, setSha256Hash] = useState<string | null>(null);
  const [md5Hash, setMd5Hash] = useState<string | null>(null);
  const [deviceBrand, setDeviceBrand] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // Live Query to detect real system block devices from backend API
  const { data: detectedDevices = [], isLoading: isLoadingDevices } = useQuery({
    queryKey: ["system-block-devices"],
    queryFn: () => casesApi.listDevices(),
    enabled: open,
    staleTime: 10000,
  });

  // Real-time SSE acquisition progress and task drawer tracking
  const sse = useTaskSSE<SSEAcquisitionEvent>({
    taskId,
    taskType: "ingestion",
    title:
      tab === "image"
        ? `Ingesting ${filePath.split("/").pop() || "Forensic Image"}`
        : `dc3dd Clone ${sourceDevice === "custom" ? customDevice : sourceDevice}`,
    onMessage: (data) => {
      if (data.sha256) setSha256Hash(data.sha256);
      if (data.md5) setMd5Hash(data.md5);
      if (data.evidence_id) setActiveEvidenceId(data.evidence_id);
      if (data.device_brand) setDeviceBrand(data.device_brand);
    },
    onError: (err) => {
      setIsProcessing(false);
      setApiError(
        err.message.includes("dc3dd")
          ? `dc3dd Clone Failed: ${err.message}. Ensure the target device is connected, unmounted, and locus has read permissions.`
          : `Acquisition Failed: ${err.message}`
      );
    },
  });

  const validateFileExtension = (pathOrName: string): boolean => {
    const lower = pathOrName.toLowerCase();
    const basename = lower.split("/").pop() || lower;
    if (basename.startsWith("ewf")) return true;
    return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
  };

  const handleFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      setSelectedFileName(file.name);
      setSelectedFileSize((file.size / (1024 * 1024)).toFixed(1) + " MB");

      // Validate extension immediately
      if (!validateFileExtension(file.name)) {
        setApiError(
          `Invalid file format "${file.name}". Supported formats: ${ALLOWED_EXTENSIONS.join(", ")}`
        );
        return;
      }

      setApiError(null);
      setFilePath(file.name);
    }
  };

  const handleStartIngestion = async () => {
    setApiError(null);

    // 1. Client-side validations
    if (tab === "image") {
      const targetPath = filePath.trim();
      if (!targetPath) {
        setApiError("Please specify or browse for a forensic disk image file.");
        return;
      }

      if (!validateFileExtension(targetPath)) {
        setApiError(
          `Unsupported file extension for "${targetPath}". Allowed formats: ${ALLOWED_EXTENSIONS.join(", ")}`
        );
        return;
      }
    } else {
      const targetDevice = sourceDevice === "custom" ? customDevice.trim() : sourceDevice.trim();
      if (!targetDevice) {
        setApiError("Please select a physical block device to clone.");
        return;
      }

      const isValidDeviceNode =
        targetDevice.startsWith("/dev/") ||
        targetDevice.startsWith("\\\\.\\") ||
        targetDevice.toLowerCase().includes("physicaldrive");

      if (!isValidDeviceNode) {
        setApiError(
          `Invalid block device identifier "${targetDevice}". Use /dev/... (Linux/macOS) or \\\\.\\PhysicalDriveN (Windows).`
        );
        return;
      }
    }

    setIsProcessing(true);
    setStatusMessage("Connecting to low-level forensic disk acquisition engine...");

    try {
      let res: { task_id: string; evidence_id: string; status: string; message: string };

      if (tab === "image") {
        res = await casesApi.ingestFile({
          case_id: caseId,
          file_path: filePath.trim(),
          investigator: investigatorName || "Forensic Officer",
        });
      } else {
        const targetDevice = sourceDevice === "custom" ? customDevice.trim() : sourceDevice.trim();
        const targetFilename =
          imageFilename.trim() ||
          `case_${caseNumber.toLowerCase().replace(/[^a-z0-9]/g, "_")}_clone.dd`;

        res = await casesApi.cloneDevice({
          case_id: caseId,
          source_device: targetDevice,
          image_filename: targetFilename,
          investigator: investigatorName || "Forensic Officer",
        });
      }

      setTaskId(res.task_id);
      setActiveEvidenceId(res.evidence_id);
    } catch (err: unknown) {
      setIsProcessing(false);
      setApiError(err instanceof Error ? err.message : "Failed to initiate acquisition.");
    }
  };

  const handleProceedToWorkspace = () => {
    onOpenChange(false);
    navigate("/investigate");
  };

  const handleReset = () => {
    setIsProcessing(false);
    setTaskId(null);
    setApiError(null);
  };

  const isCompleted = sse.stage === "COMPLETED" || sse.stage === "DONE" || sse.isCompleted;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="size-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <HardDrive className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold font-heading flex items-center gap-2">
                <span>Evidence Acquisition & Ingestion</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {caseNumber}
                </span>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Ingest raw forensic images or clone physical CCTV/DVR storage media with live
                dual-hashing.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {apiError && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-start gap-2.5">
            <AlertCircle className="size-4 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold">Acquisition Error</p>
              <p className="text-[11px] leading-relaxed opacity-90">{apiError}</p>
            </div>
          </div>
        )}

        {!isProcessing ? (
          <div className="space-y-4 py-2">
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="grid grid-cols-2 bg-secondary">
                <TabsTrigger value="image" className="gap-1.5 text-xs">
                  <FileCode2 className="size-3.5" />
                  Raw Image (.dd / .raw)
                </TabsTrigger>
                <TabsTrigger value="device" className="gap-1.5 text-xs">
                  <HardDrive className="size-3.5" />
                  Physical Drive (dc3dd)
                </TabsTrigger>
              </TabsList>

              {/* Tab 1: Image File */}
              <TabsContent value="image" className="space-y-3 pt-3">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-foreground flex items-center justify-between">
                    <span>Forensic Disk Image File *</span>
                    <span className="text-[10px] text-muted-foreground font-mono">
                      {ALLOWED_EXTENSIONS.join(" ")}
                    </span>
                  </label>

                  {/* Hidden file picker */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ALLOWED_EXTENSIONS.join(",")}
                    onChange={handleFilePicked}
                    className="hidden"
                  />

                  <div className="flex gap-2">
                    <Input
                      value={filePath}
                      onChange={(e) => {
                        setFilePath(e.target.value);
                        setSelectedFileName(null);
                        setSelectedFileSize(null);
                        setApiError(null);
                      }}
                      placeholder="/home/evidence/case_001.dd or browse..."
                      className="font-mono text-xs flex-1"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setExplorerOpen(true)}
                      className="gap-1 text-xs shrink-0"
                      title="Browse server forensic directories"
                    >
                      <FolderSearch className="size-3.5 text-primary" />
                      Browse Server...
                    </Button>
                  </div>

                  {selectedFileName && (
                    <div className="p-2.5 rounded-lg bg-secondary/70 border border-border text-xs flex items-center justify-between">
                      <div className="flex items-center gap-2 truncate">
                        <FileCode2 className="size-3.5 text-primary shrink-0" />
                        <span className="font-mono text-foreground truncate">
                          {selectedFileName}
                        </span>
                      </div>
                      {selectedFileSize && (
                        <span className="font-mono text-muted-foreground text-[11px] shrink-0">
                          {selectedFileSize}
                        </span>
                      )}
                    </div>
                  )}

                  <p className="text-[11px] text-muted-foreground">
                    Supports raw bitstream disk dumps (.dd, .raw, .img, .bin, .iso, .001, .dav).
                    Computes simultaneous SHA-256 + MD5.
                  </p>
                </div>
              </TabsContent>

              {/* Tab 2: Physical Device with Live Hardware Discovery */}
              <TabsContent value="device" className="space-y-3 pt-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-foreground">
                      Source Physical Block Device *
                    </label>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      {isLoadingDevices
                        ? "Scanning devices..."
                        : `${detectedDevices.length} detected`}
                    </span>
                  </div>

                  <Select
                    value={sourceDevice}
                    onValueChange={(val: string | null) => setSourceDevice(val || "")}
                  >
                    <SelectTrigger className="w-full font-mono text-xs">
                      <SelectValue placeholder="Select connected hardware drive..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectLabel>Connected Block Devices</SelectLabel>
                        {detectedDevices.map((dev) => (
                          <SelectItem key={dev.path} value={dev.path}>
                            <div className="flex items-center gap-2">
                              {dev.transport === "usb" || dev.removable ? (
                                <Usb className="size-3 text-cyan-400" />
                              ) : (
                                <Cpu className="size-3 text-primary" />
                              )}
                              <span className="font-bold">{dev.path}</span>
                              <span className="text-muted-foreground">
                                ({dev.size}
                                {dev.model ? ` — ${dev.model}` : ""})
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                        {detectedDevices.length === 0 && (
                          <SelectItem value="/dev/sdb">
                            /dev/sdb — Secondary SATA / USB Drive (Standard)
                          </SelectItem>
                        )}
                        <SelectItem value="custom">Enter Custom Device Node...</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                {sourceDevice === "custom" && (
                  <div className="space-y-1.5 animate-in fade-in duration-150">
                    <label className="text-xs font-medium text-foreground">
                      Custom Block Device Node *
                    </label>
                    <Input
                      value={customDevice}
                      onChange={(e) => setCustomDevice(e.target.value)}
                      placeholder="/dev/disk/by-id/..."
                      className="font-mono text-xs"
                    />
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground">
                    Destination Image Filename (Optional)
                  </label>
                  <Input
                    value={imageFilename}
                    onChange={(e) => setImageFilename(e.target.value)}
                    placeholder={`case_${caseNumber.toLowerCase().replace(/[^a-z0-9]/g, "_")}_clone.dd`}
                    className="font-mono text-xs"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Uses forensic <code className="text-primary font-mono">dc3dd</code> with
                    real-time stderr telemetry and hardware write-block verification.
                  </p>
                </div>
              </TabsContent>
            </Tabs>

            <div className="pt-2 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleStartIngestion} className="gap-2 font-semibold">
                <ShieldCheck className="size-4" />
                Start Cryptographic Ingestion →
              </Button>
            </div>
          </div>
        ) : (
          /* Live Streaming Telemetry Card matching Excalidraw Scenario 1 */
          <div className="space-y-4 py-3 animate-in fade-in duration-200">
            <div className="p-4 rounded-xl bg-secondary/60 border border-border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {isCompleted ? (
                    <CheckCircle2 className="size-4 text-emerald-400" />
                  ) : (
                    <Activity className="size-4 text-cyan-400 animate-spin" />
                  )}
                  <span className="text-xs font-mono font-bold text-foreground">
                    {sse.stage} {sse.progress}%
                  </span>
                </div>

                {sse.speedMbps > 0 && (
                  <span className="text-xs font-mono text-cyan-400 font-semibold">
                    {sse.speedMbps.toFixed(1)} MB/s
                  </span>
                )}
              </div>

              <Progress value={sse.progress} className="h-2" />

              <p className="text-xs text-muted-foreground font-mono">
                {sse.message ||
                  statusMessage ||
                  "Parsing sectors and calculating cryptographic hashes..."}
              </p>
            </div>

            {/* Dual-Hash Cryptographic Vault Display */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-card border border-border space-y-1">
                <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Lock className="size-3 text-primary" />
                    SHA-256 Hash
                  </span>
                  {sha256Hash && <span className="text-emerald-400 font-bold">✓ Sealed</span>}
                </div>
                <div className="font-mono text-xs truncate text-foreground select-all bg-secondary/50 px-2 py-1 rounded">
                  {sha256Hash || "Computing streaming SHA-256..."}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-card border border-border space-y-1">
                <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Lock className="size-3 text-primary" />
                    MD5 Hash
                  </span>
                  {md5Hash && <span className="text-emerald-400 font-bold">✓ Sealed</span>}
                </div>
                <div className="font-mono text-xs truncate text-foreground select-all bg-secondary/50 px-2 py-1 rounded">
                  {md5Hash || "Computing streaming MD5..."}
                </div>
              </div>
            </div>

            {deviceBrand && (
              <div className="p-2.5 rounded-lg bg-primary/10 border border-primary/20 text-xs text-primary flex items-center justify-between font-mono">
                <span>Proprietary DVR Format Detected:</span>
                <span className="font-bold">{deviceBrand}</span>
              </div>
            )}

            <div className="pt-2 flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="xs" onClick={handleReset} className="gap-1 text-xs">
                  <RefreshCcw className="size-3" />
                  Reconfigure
                </Button>
                <span className="text-[11px] font-mono text-muted-foreground">
                  Task: {taskId?.slice(0, 12)}...
                </span>
              </div>

              <Button
                size="sm"
                onClick={handleProceedToWorkspace}
                className="gap-2 bg-primary text-primary-foreground font-semibold shadow-md shadow-primary/20"
              >
                Enter Investigation Workspace
                <ArrowRight className="size-3.5" />
              </Button>
            </div>
          </div>
        )}
      </DialogContent>

      <ServerFilePickerModal
        open={explorerOpen}
        onOpenChange={setExplorerOpen}
        onSelect={(selectedPath, size) => {
          setFilePath(selectedPath);
          setSelectedFileName(selectedPath.split("/").pop() || selectedPath);
          setSelectedFileSize(size || null);
          setApiError(null);
        }}
      />
    </Dialog>
  );
}
