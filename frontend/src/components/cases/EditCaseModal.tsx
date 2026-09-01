import { useState, useEffect } from "react";
import { useForm } from "@tanstack/react-form";
import { z } from "zod";
import { FolderEdit, Loader2, Save, User, ShieldCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../ui/select";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { casesApi } from "../../api/cases";
import type { Case, CaseStatus } from "../../types/case";

const editCaseSchema = z.object({
  case_name: z.string().min(3, "Case name must be at least 3 characters").max(255),
  investigator: z.string().min(2, "Investigator name must be at least 2 characters").max(128),
  description: z.string(),
  status: z.enum(["ACTIVE", "ARCHIVED", "CLOSED"]),
});

interface EditCaseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseItem: Case | null;
  onSuccess: () => void;
}

function formatFieldErrors(errors: unknown[]): string {
  if (!errors || errors.length === 0) return "";
  return errors
    .map((err) => {
      if (typeof err === "string") return err;
      if (typeof err === "object" && err !== null) {
        const obj = err as Record<string, unknown>;
        if (typeof obj.message === "string") return obj.message;
        if (typeof obj.msg === "string") return obj.msg;
        return JSON.stringify(err);
      }
      return String(err);
    })
    .join(", ");
}

export function EditCaseModal({ open, onOpenChange, caseItem, onSuccess }: EditCaseModalProps) {
  const [apiError, setApiError] = useState<string | null>(null);

  const form = useForm({
    defaultValues: {
      case_name: caseItem?.case_name || "",
      investigator: caseItem?.investigator || "",
      description: caseItem?.description || "",
      status: (caseItem?.status || "ACTIVE") as CaseStatus,
    },
    validators: {
      onChange: editCaseSchema,
    },
    onSubmit: async ({ value }) => {
      if (!caseItem) return;
      setApiError(null);

      try {
        await casesApi.updateCase(caseItem.id, {
          case_name: value.case_name.trim(),
          investigator: value.investigator.trim(),
          description: value.description?.trim() || undefined,
          status: value.status,
        });

        onSuccess();
        onOpenChange(false);
      } catch (err: unknown) {
        setApiError(err instanceof Error ? err.message : "Failed to update case dossier.");
      }
    },
  });

  // Sync form when caseItem changes
  useEffect(() => {
    if (caseItem) {
      form.reset({
        case_name: caseItem.case_name,
        investigator: caseItem.investigator,
        description: caseItem.description || "",
        status: caseItem.status,
      });
    }
  }, [caseItem, form]);

  if (!caseItem) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="size-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <FolderEdit className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold font-heading flex items-center gap-2">
                <span>Edit Case Dossier</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {caseItem.case_number}
                </span>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Update forensic metadata, lead investigator, narrative, or dossier status.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {apiError && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-xs">
            {apiError}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            form.handleSubmit();
          }}
          className="space-y-4 py-2"
        >
          {/* Incident / Case Title */}
          <form.Field name="case_name">
            {(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground flex justify-between">
                  <span>Incident / Case Title *</span>
                  <span className="text-[10px] text-muted-foreground">Required</span>
                </label>
                <Input
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  placeholder="e.g. Bank Vault Intrusion Analysis"
                  className="text-xs font-medium"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="text-[11px] text-destructive">
                    {formatFieldErrors(field.state.meta.errors)}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {/* Lead Investigator */}
          <form.Field name="investigator">
            {(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                  <User className="size-3.5 text-primary" />
                  <span>Lead Investigator *</span>
                </label>
                <Input
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  placeholder="e.g. Det. Sarah Jenkins (Badge #4092)"
                  className="text-xs"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="text-[11px] text-destructive">
                    {formatFieldErrors(field.state.meta.errors)}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {/* Status Selector */}
          <form.Field name="status">
            {(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                  <ShieldCheck className="size-3.5 text-cyan-400" />
                  <span>Dossier Status</span>
                </label>
                <Select
                  value={field.state.value}
                  onValueChange={(val: string | null) =>
                    field.handleChange((val || "ACTIVE") as CaseStatus)
                  }
                >
                  <SelectTrigger className="w-full text-xs font-mono">
                    <SelectValue placeholder="Select status..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ACTIVE">ACTIVE (Under Ongoing Investigation)</SelectItem>
                    <SelectItem value="ARCHIVED">
                      ARCHIVED (Analysis Complete / Read-Only)
                    </SelectItem>
                    <SelectItem value="CLOSED">CLOSED (Legal Dossier Concluded)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </form.Field>

          {/* Narrative / Description */}
          <form.Field name="description">
            {(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  Case Narrative / Scope Notes
                </label>
                <Textarea
                  value={field.state.value || ""}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  rows={3}
                  placeholder="Summary of seized DVR evidence, target timeframe, and key objectives..."
                  className="text-xs resize-none"
                />
              </div>
            )}
          </form.Field>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <form.Subscribe selector={(state) => [state.isSubmitting]}>
              {([isSubmitting]) => (
                <Button
                  type="submit"
                  size="sm"
                  disabled={isSubmitting}
                  className="gap-1.5 font-semibold"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="size-3.5" />
                      Save Changes
                    </>
                  )}
                </Button>
              )}
            </form.Subscribe>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
