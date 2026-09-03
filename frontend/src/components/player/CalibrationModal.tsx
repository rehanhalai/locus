import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Badge } from "../ui/badge";
import { Clock, RotateCcw, Check, Plus, Minus } from "lucide-react";
import { videoApi } from "../../api/video";
import { useCaseStore } from "../../stores/useCaseStore";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

interface CalibrationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  evidenceId: string;
  initialCameraId?: number;
}

const CAMERA_NAMES: Record<number, string> = {
  1: "Main Entrance",
  2: "Cash Counter",
  3: "Vault Room",
  4: "Perimeter Street",
};

export function CalibrationModal({
  open,
  onOpenChange,
  evidenceId,
  initialCameraId = 1,
}: CalibrationModalProps) {
  const queryClient = useQueryClient();
  const [selectedCameraId, setSelectedCameraId] = useState<number>(initialCameraId);
  const [offsetSeconds, setOffsetSeconds] = useState<number>(0);
  const [reason, setReason] = useState<string>("");

  const investigatorName = useCaseStore((s) => s.investigatorName);
  const cameraOffsets = useCaseStore((s) => s.cameraOffsets);
  const setCameraOffset = useCaseStore((s) => s.setCameraOffset);

  // Fetch active calibrations for evidence
  const { data: calibrations } = useQuery({
    queryKey: ["calibrations", evidenceId],
    queryFn: () => (evidenceId ? videoApi.getCalibrations(evidenceId) : []),
    enabled: !!evidenceId && open,
  });

  // When switching selected camera inside modal, sync existing offset
  const handleSelectCamera = (camId: number) => {
    setSelectedCameraId(camId);
    const existing = calibrations?.find((c) => c.camera_id === camId);
    if (existing) {
      setOffsetSeconds(existing.offset_seconds);
      setReason(existing.reason || "");
    } else {
      setOffsetSeconds(cameraOffsets[camId] || 0);
      setReason("");
    }
  };

  // Set calibration mutation
  const setCalibrationMutation = useMutation({
    mutationFn: async () => {
      return await videoApi.setCalibration({
        evidence_id: evidenceId,
        camera_id: selectedCameraId,
        offset_seconds: offsetSeconds,
        reason: reason || "Forensic clock drift synchronization",
        investigator: investigatorName || "Forensic Officer",
      });
    },
    onSuccess: (data) => {
      setCameraOffset(data.camera_id, data.offset_seconds);
      queryClient.invalidateQueries({ queryKey: ["calibrations", evidenceId] });
      queryClient.invalidateQueries({ queryKey: ["timeline", evidenceId] });
      onOpenChange(false);
    },
  });

  // Reset calibration mutation
  const resetCalibrationMutation = useMutation({
    mutationFn: async () => {
      return await videoApi.resetCalibration(
        evidenceId,
        selectedCameraId,
        investigatorName || "Forensic Officer"
      );
    },
    onSuccess: () => {
      setCameraOffset(selectedCameraId, 0);
      setOffsetSeconds(0);
      queryClient.invalidateQueries({ queryKey: ["calibrations", evidenceId] });
      queryClient.invalidateQueries({ queryKey: ["timeline", evidenceId] });
      onOpenChange(false);
    },
  });

  const adjustOffset = (delta: number) => {
    setOffsetSeconds((prev) => parseFloat((prev + delta).toFixed(3)));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Clock className="size-4.5 text-primary" />
            Camera Clock Calibration & Offset
          </DialogTitle>
          <DialogDescription className="text-xs">
            Adjust timestamp drift for desynchronized DVR channel clocks. Changes are logged to the
            tamper-evident forensic audit trail.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Camera Selector Tabs */}
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1.5 block">
              Target Camera Channel
            </label>
            <div className="grid grid-cols-4 gap-1.5 bg-secondary/60 p-1 rounded-lg border border-border">
              {[1, 2, 3, 4].map((camId) => {
                const isSelected = selectedCameraId === camId;
                const offset = cameraOffsets[camId] || 0;
                return (
                  <button
                    key={camId}
                    type="button"
                    onClick={() => handleSelectCamera(camId)}
                    className={`flex flex-col items-center py-1.5 px-1 rounded-md text-xs font-medium transition-all ${
                      isSelected
                        ? "bg-background text-foreground shadow-xs font-bold border border-border"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <span>CH {camId}</span>
                    {offset !== 0 && (
                      <span className="text-[9px] font-mono text-amber-400">
                        {offset > 0 ? `+${offset}s` : `${offset}s`}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] font-mono text-muted-foreground mt-1 text-center">
              Channel: {CAMERA_NAMES[selectedCameraId] || `Camera ${selectedCameraId}`}
            </p>
          </div>

          {/* Time Offset Input & Quick Adjustment Controls */}
          <div className="space-y-2 bg-secondary/40 p-3 rounded-lg border border-border">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold">Clock Time Offset (Seconds)</label>
              <Badge
                variant="outline"
                className={`font-mono text-xs ${
                  offsetSeconds === 0
                    ? "text-muted-foreground"
                    : offsetSeconds > 0
                      ? "text-emerald-400 border-emerald-500/40 bg-emerald-500/10"
                      : "text-amber-400 border-amber-500/40 bg-amber-500/10"
                }`}
              >
                {offsetSeconds > 0 ? `+${offsetSeconds}s` : `${offsetSeconds}s`}
              </Badge>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon-xs"
                onClick={() => adjustOffset(-1)}
                title="Subtract 1 second"
              >
                <Minus className="size-3.5" />
              </Button>

              <Input
                type="number"
                step="0.1"
                value={offsetSeconds}
                onChange={(e) => setOffsetSeconds(parseFloat(e.target.value) || 0)}
                className="font-mono text-center text-sm font-bold"
              />

              <Button
                variant="outline"
                size="icon-xs"
                onClick={() => adjustOffset(1)}
                title="Add 1 second"
              >
                <Plus className="size-3.5" />
              </Button>
            </div>

            {/* Quick Offset Increments */}
            <div className="flex items-center justify-between gap-1 pt-1">
              {[-60, -10, -1, 1, 10, 60].map((delta) => (
                <button
                  key={delta}
                  type="button"
                  onClick={() => adjustOffset(delta)}
                  className="flex-1 py-1 rounded bg-background hover:bg-secondary text-[10px] font-mono border border-border text-muted-foreground hover:text-foreground transition-colors"
                >
                  {delta > 0 ? `+${delta}s` : `${delta}s`}
                </button>
              ))}
            </div>
          </div>

          {/* Forensic Justification / Reason Input */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-muted-foreground">
              Forensic Justification / Reference Source
            </label>
            <Input
              placeholder="e.g. Wall clock reference at 14:02:15 UTC or NIST GPS time sync"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="text-xs"
            />
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
          <Button
            variant="ghost"
            size="xs"
            onClick={() => resetCalibrationMutation.mutate()}
            disabled={resetCalibrationMutation.isPending || offsetSeconds === 0}
            className="text-destructive hover:text-destructive text-xs gap-1"
          >
            <RotateCcw className="size-3" />
            Reset to Baseline
          </Button>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="xs" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              size="xs"
              onClick={() => setCalibrationMutation.mutate()}
              disabled={setCalibrationMutation.isPending}
              className="gap-1.5 font-semibold"
            >
              <Check className="size-3.5" />
              Apply Offset
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
