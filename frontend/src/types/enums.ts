/**
 * Mirrors app/models/enums.py exactly — the backend's frozen source of
 * truth (docs/API_CONTRACT.md: "closed sets ... do not add client-side
 * handling for values that don't exist there").
 */

export type Role =
  | "PLATFORM_OWNER"
  | "ADMIN"
  | "SUB_ADMIN"
  | "MANAGER"
  | "RESIDENT"
  | "SECURITY_GUARD";

export type SocietyStatus = "PENDING" | "ACTIVE" | "SUSPENDED";
export type UserStatus = "PENDING" | "ACTIVE" | "REJECTED" | "INACTIVE";
export type LocationType = "WING" | "ROW";
export type HouseType = "FLAT" | "BUNGALOW";
export type RelationshipType = "OWNER" | "TENANT";
export type RoleRequestStatus = "PENDING" | "APPROVED" | "REJECTED";
export type MaintenanceDueStatus = "PENDING" | "PAID";
export type PaymentMethod = "MOCK_ONLINE" | "MANUAL_UPI" | "MANUAL_CASH";
export type PaymentStatus = "PENDING_APPROVAL" | "PAID" | "REJECTED";
export type ProofType = "UPI_SCREENSHOT" | "CASH_RECEIPT";
export type EntryType = "INCOME" | "EXPENSE";
export type EntrySource = "MANUAL" | "MAINTENANCE_PAYMENT" | "EXPENSE_BILL" | "ADJUSTMENT";
export type TodoStatus = "PENDING" | "IN_PROGRESS" | "DONE";
export type ComplaintStatus = "OPEN" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
export type VisitorStatus = "PRE_APPROVED" | "EXPECTED" | "ENTERED" | "EXITED" | "CANCELLED";
export type BookingStatus = "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
export type ProposalScope = "SOCIETY" | "WING" | "ROW";
export type ProposalStatus = "OPEN" | "APPROVED" | "WITHDRAWN";
export type Vote = "APPROVE" | "REJECT";
export type ExpenseBillStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
export type Decision = "APPROVE" | "REJECT";

export interface Page<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface ApiError {
  detail: string | { loc: (string | number)[]; msg: string; type: string }[];
}
