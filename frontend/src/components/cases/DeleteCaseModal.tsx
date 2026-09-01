import { useState } from "react";
import { Trash2, AlertTriangle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { casesApi } from "../../api/cases";
import type { Case } from "../../types/case";

interface DeleteCaseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  caseItem: Case | null;
  onSuccess: () => void;
}

export function DeleteCaseModal({ open, onOpenChange, caseItem, onSuccess }: DeleteCaseModalProps) {
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  if (!caseItem) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    setApiError(null);

    try {
      await casesApi.deleteCase(caseItem.id);
      onSuccess();
      onOpenChange(false);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Failed to delete case.");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="size-10 rounded-xl bg-destructive/10 flex items-center justify-center text-destructive">
              <Trash2 className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-semibold font-heading text-destructive flex items-center gap-2">
                <span>Delete Case Dossier</span>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                This action is irreversible and permanently deletes the case record and its forensic
                audit logs.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {apiError && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-xs">
            {apiError}
          </div>
        )}

        <div className="p-3.5 rounded-lg bg-secondary/40 border border-border space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-muted-foreground">Case Number:</span>
            <span className="font-bold text-foreground">{caseItem.case_number}</span>
          </div>
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-muted-foreground">Incident Title:</span>
            <span className="font-bold text-foreground truncate max-w-[200px]">
              {caseItem.case_name}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-muted-foreground">Lead Investigator:</span>
            <span className="text-foreground">{caseItem.investigator}</span>
          </div>
        </div>

        <div className="flex items-start gap-2 p-2.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs">
          <AlertTriangle className="size-4 shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            All carved evidence clips, YOLO detections, and timeline calibrations associated with
            this case will be deleted from the database.
          </p>
        </div>

        <DialogFooter className="pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={isDeleting}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            disabled={isDeleting}
            onClick={handleDelete}
            className="gap-1.5 font-semibold shadow-xs"
          >
            {isDeleting ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                <Trash2 className="size-3.5" />
                Confirm Delete
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
