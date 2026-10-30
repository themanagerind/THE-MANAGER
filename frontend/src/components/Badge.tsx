const tones = {
  neutral: "bg-line text-navy-muted",
  navy: "bg-navy/10 text-navy",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
};

/** Maps backend status strings (PaymentStatus, ComplaintStatus, etc — see
 * docs/API_CONTRACT.md "closed sets") to a visual tone. Unknown values fall
 * back to neutral rather than throwing, since new statuses should never
 * crash the UI even if this map lags a backend addition. */
const statusTone: Record<string, keyof typeof tones> = {
  PENDING: "warning",
  PENDING_APPROVAL: "warning",
  DRAFT: "neutral",
  OPEN: "navy",
  IN_PROGRESS: "navy",
  ACTIVE: "success",
  APPROVED: "success",
  PAID: "success",
  RESOLVED: "success",
  DONE: "success",
  ENTERED: "success",
  EXITED: "neutral",
  REJECTED: "danger",
  CANCELLED: "neutral",
  CLOSED: "neutral",
  SUSPENDED: "danger",
  INACTIVE: "neutral",
  WITHDRAWN: "neutral",
  EXPECTED: "navy",
  PRE_APPROVED: "navy",
};

export function Badge({ status, children }: { status?: string; children: React.ReactNode }) {
  const tone = status ? statusTone[status] ?? "neutral" : "neutral";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}
