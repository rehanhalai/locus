import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import { z } from "zod";
import { FolderPlus, AlertCircle, Loader2 } from "lucide-react";
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
import { Textarea } from "../ui/textarea";
import { casesApi } from "../../api/cases";
import { useCaseStore } from "../../stores/useCaseStore";
import type { Case } from "../../types/case";

const caseCreateSchema = z.object({
  case_number: z
    .string()
    .min(3, "Case number must be at least 3 characters")
    .max(30, "Case number too long"),
  case_name: z
    .string()
    .min(3, "Case name must be at least 3 characters")
    .max(100, "Case name too long"),
  investigator: z.string().min(2, "Investigator name is required"),
  description: z.string().optional(),
});

type CaseCreateFormValues = z.infer<typeof caseCreateSchema>;

interface CreateCaseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCaseCreated: (createdCase: Case) => void;
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

export function CreateCaseModal({ open, onOpenChange, onCaseCreated }: CreateCaseModalProps) {
  const investigatorName = useCaseStore((s) => s.investigatorName);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const form = useForm({
    defaultValues: {
      case_number: "CAS-2026-001",
      case_name: "",
      investigator: investigatorName || "Investigator Pande",
      description: "",
    } as CaseCreateFormValues,
    validators: {
      onChange: caseCreateSchema,
    },
    onSubmit: async ({ value }) => {
      setApiError(null);
      setIsSubmitting(true);
      try {
        const newCase = await casesApi.createCase({
          case_number: value.case_number.trim(),
          case_name: value.case_name.trim(),
          investigator: value.investigator.trim(),
          description: value.description?.trim() || undefined,
        });

        onCaseCreated(newCase);
        onOpenChange(false);
        form.reset();
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "Failed to create case dossier. Please try again.";
        setApiError(msg);
      } finally {
        setIsSubmitting(false);
      }
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="size-9 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <FolderPlus className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold font-heading">
                Initialize New Case Dossier
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Create a forensic case container to bind ingested CCTV images, sector maps, and
                audit logs.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {apiError && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{apiError}</span>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
            void form.handleSubmit();
          }}
          className="space-y-4 py-2"
        >
          {/* Case Number */}
          <form.Field
            name="case_number"
            children={(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-mono font-medium text-foreground flex items-center justify-between">
                  <span>Case Reference Number *</span>
                  <span className="text-[10px] text-muted-foreground">e.g. CAS-2026-001</span>
                </label>
                <Input
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  placeholder="CAS-2026-001"
                  className="font-mono text-xs"
                />
                {field.state.meta.errors.length > 0 ? (
                  <p className="text-[11px] text-destructive">
                    {formatFieldErrors(field.state.meta.errors)}
                  </p>
                ) : null}
              </div>
            )}
          />

          {/* Case Name */}
          <form.Field
            name="case_name"
            children={(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  Case / Incident Name *
                </label>
                <Input
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  placeholder="e.g. Downtown Jewelry Store Incident"
                  className="text-xs"
                />
                {field.state.meta.errors.length > 0 ? (
                  <p className="text-[11px] text-destructive">
                    {formatFieldErrors(field.state.meta.errors)}
                  </p>
                ) : null}
              </div>
            )}
          />

          {/* Investigator */}
          <form.Field
            name="investigator"
            children={(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  Lead Forensic Investigator *
                </label>
                <Input
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  placeholder="Officer / Investigator Name"
                  className="text-xs"
                />
                {field.state.meta.errors.length > 0 ? (
                  <p className="text-[11px] text-destructive">
                    {formatFieldErrors(field.state.meta.errors)}
                  </p>
                ) : null}
              </div>
            )}
          />

          {/* Description */}
          <form.Field
            name="description"
            children={(field) => (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">
                  Case Description & Notes (Optional)
                </label>
                <Textarea
                  value={field.state.value || ""}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  rows={3}
                  placeholder="Brief synopsis of seized DVR/NVR hardware or incident timeline"
                  className="text-xs resize-none"
                />
              </div>
            )}
          />

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isSubmitting}
              className="gap-1.5 font-semibold"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  Creating Dossier...
                </>
              ) : (
                "Create Case Dossier →"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
