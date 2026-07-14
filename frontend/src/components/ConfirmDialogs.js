import { useState, useEffect } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

export const ConfirmDialog = ({ open, onOpenChange, title, description, confirmLabel = 'Confirm', onConfirm, destructive = true, testIdPrefix = 'confirm' }) => (
  <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent className="bg-bg-surface border-border-color">
      <AlertDialogHeader>
        <AlertDialogTitle className="text-text-primary">{title}</AlertDialogTitle>
        <AlertDialogDescription className="text-text-secondary">{description}</AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter>
        <AlertDialogCancel data-testid={`${testIdPrefix}-cancel-btn`}>Cancel</AlertDialogCancel>
        <AlertDialogAction onClick={onConfirm} data-testid={`${testIdPrefix}-confirm-btn`}
          className={destructive ? 'bg-danger text-white hover:bg-danger/90' : ''}>
          {confirmLabel}
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);

export const ReasonDialog = ({ open, onOpenChange, title, description, placeholder = 'Enter reason...', submitLabel = 'Submit', onSubmit, testIdPrefix = 'reason' }) => {
  const [reason, setReason] = useState('');

  useEffect(() => { if (!open) setReason(''); }, [open]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reason.trim()) return;
    onSubmit(reason.trim());
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-bg-surface border-border-color sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle className="text-text-primary">{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-1">
          {description && <p className="text-sm text-text-secondary">{description}</p>}
          <textarea value={reason} onChange={(e) => setReason(e.target.value)}
            data-testid={`${testIdPrefix}-input`}
            className="input-field w-full min-h-[90px] resize-none" placeholder={placeholder} autoFocus required />
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => onOpenChange(false)} data-testid={`${testIdPrefix}-cancel-btn`}
              className="btn-secondary">Cancel</button>
            <button type="submit" disabled={!reason.trim()} data-testid={`${testIdPrefix}-submit-btn`}
              className="btn-primary disabled:opacity-50">{submitLabel}</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
