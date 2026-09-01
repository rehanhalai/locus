import { useState, useRef } from "react";
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
import { subscribeSSE } from "../../api/sse";
import { useCaseStore } from "../../stores/useCaseStore";
import { useNavigate } from "react-router-dom";

const ALLOWED_EXTENSIONS = [".dd", ".raw", ".img", ".bin", ".iso", ".001", ".e01", ".vmdk", ".vhd"];

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
  sha256_hash?: string;
  md5_hash?: string;
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
  const addOrUpdateTask = useCaseStore((s) => s.addOrUpdateTask);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<string>("image");
  const [filePath, setFilePath] = useState<string>("");
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileSize, setSelectedFileSize] = useState<string | null>(null);

  const [sourceDevice, setSourceDevice] = useState<string>("");
  const [customDevice, setCustomDevice] = useState<string>("");
  const [imageFilename, setImageFilename] = useState<string>("");

  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [speedMbps, setSpeedMbps] = useState<number>(0);
  const [stage, setStage] = useState<string>("IDLE");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [sha256Hash, setSha256Hash] = useState<string | null>(null);
  const [md5Hash, setMd5Hash] = useState<string | null>(null);
  const [deviceBrand, setDeviceBrand] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const validateFileExtension = (pathOrName: string): boolean => {
    const lower = pathOrName.toLowerCase();
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
      // In browsers, file.name or relative path can be used
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

      if (!targetDevice.startsWith("/dev/")) {
        setApiError(
          `Invalid block device identifier "${targetDevice}". Must start with /dev/ (e.g. /dev/sdb).`
        );
        return;
      }
    }

    setIsProcessing(true);
    setProgress(0);
    setStage("INITIALIZING");
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

      addOrUpdateTask({
        task_id: res.task_id,
        type: "ingestion",
        title:
          tab === "image"
            ? `Ingesting ${filePath.split("/").pop() || "Forensic Image"}`
            : `dc3dd Clone ${sourceDevice === "custom" ? customDevice : sourceDevice}`,
        status: "PROCESSING",
        progress_percent: 0,
        started_at: new Date().toISOString(),
      });

      // 2. Subscribe to real-time SSE stream with failure detection
      subscribeSSE<SSEAcquisitionEvent>(`/acquisition/stream/${res.task_id}`, {
        onMessage: (data) => {
          const pct = data.percentage ?? data.progress_percent ?? 0;
          const spd = data.speed_mbps ?? data.speed_mb_s ?? data.rate_mb_s ?? 0;
          const currentStage = data.stage ?? data.status ?? "INGESTING";

          setProgress(Math.min(100, Math.max(0, Math.round(pct))));
          setSpeedMbps(spd);
          setStage(currentStage);
          if (data.message) setStatusMessage(data.message);
          if (data.sha256_hash) setSha256Hash(data.sha256_hash);
          if (data.md5_hash) setMd5Hash(data.md5_hash);
          if (data.device_brand) setDeviceBrand(data.device_brand);

          addOrUpdateTask({
            task_id: res.task_id,
            type: "ingestion",
            title:
              tab === "image"
                ? `Ingesting ${filePath.split("/").pop() || "Forensic Image"}`
                : `dc3dd Clone ${sourceDevice === "custom" ? customDevice : sourceDevice}`,
            status:
              currentStage === "DONE" || currentStage === "COMPLETED" ? "COMPLETED" : "PROCESSING",
            progress_percent: Math.min(100, Math.max(0, Math.round(pct))),
            speed_mbps: spd,
            message: data.message,
            started_at: new Date().toISOString(),
          });
        },
        onComplete: () => {
          setProgress(100);
          setStage("COMPLETED");
          setStatusMessage("Evidence ingestion & dual-hashing complete. Ready for analysis.");
        },
        onError: (err) => {
          setIsProcessing(false);
          setApiError(
            err.message.includes("dc3dd")
              ? `dc3dd Clone Failed: ${err.message}. Ensure the target device is connected, not locked by another process, and locus has appropriate read permissions.`
              : `Acquisition Failed: ${err.message}`
          );
        },
      });
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
    setProgress(0);
    setStage("IDLE");
    setApiError(null);
  };

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
                      }}
                      placeholder="e.g. /data/evidence/dahua_dvr_raw.dd"
                      className="font-mono text-xs flex-1"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      className="gap-1.5 shrink-0 text-xs"
                    >
                      <FolderSearch className="size-3.5" />
                      Browse...
                    </Button>
                  </div>

                  {selectedFileName && (
                    <div className="p-2 rounded bg-secondary/50 border border-border text-[11px] font-mono flex items-center justify-between">
                      <span className="text-primary truncate">{selectedFileName}</span>
                      <span className="text-muted-foreground shrink-0">{selectedFileSize}</span>
                    </div>
                  )}

                  <p className="text-[11px] text-muted-foreground">
                    Supports bitstream disk dumps (.dd, .raw, .img, .bin, .iso, .001, .e01).
                    Computes simultaneous SHA-256 + MD5.
                  </p>
                </div>
              </TabsContent>

              {/* Tab 2: Physical Device */}
              <TabsContent value="device" className="space-y-3 pt-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground flex items-center justify-between">
                    <span>Source Block Device *</span>
                    <span className="text-[10px] text-muted-foreground">
                      Physical DVR/CCTV Drive
                    </span>
                  </label>

                  <Select
                    value={sourceDevice}
                    onValueChange={(val: string | null) => setSourceDevice(val || "")}
                  >
                    <SelectTrigger className="w-full font-mono text-xs">
                      <SelectValue placeholder="Select physical drive..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectLabel>Common Hardware Nodes</SelectLabel>
                        <SelectItem value="/dev/sdb">
                          /dev/sdb — Secondary SATA / USB Drive
                        </SelectItem>
                        <SelectItem value="/dev/sdc">/dev/sdc — External Mass Storage</SelectItem>
                        <SelectItem value="/dev/sdd">/dev/sdd — Removable Flash Storage</SelectItem>
                        <SelectItem value="/dev/nvme0n1">
                          /dev/nvme0n1 — NVMe Storage Module
                        </SelectItem>
                        <SelectItem value="custom">Enter Custom Device Path...</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                {sourceDevice === "custom" && (
                  <div className="space-y-1.5 animate-in fade-in duration-150">
                    <label className="text-xs font-medium text-foreground">
                      Custom Device Path *
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
                  {stage === "COMPLETED" || stage === "DONE" ? (
                    <CheckCircle2 className="size-4 text-emerald-400" />
                  ) : (
                    <Activity className="size-4 text-cyan-400 animate-spin" />
                  )}
                  <span className="text-xs font-mono font-bold text-foreground">
                    {stage} {progress}%
                  </span>
                </div>

                {speedMbps > 0 && (
                  <span className="text-xs font-mono text-cyan-400 font-semibold">
                    {speedMbps.toFixed(1)} MB/s
                  </span>
                )}
              </div>

              <Progress value={progress} className="h-2" />

              <p className="text-xs text-muted-foreground font-mono">
                {statusMessage || "Parsing sectors and calculating cryptographic hashes..."}
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
    </Dialog>
  );
}
