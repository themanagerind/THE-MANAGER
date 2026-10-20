# THE-MANAGER — Backend API Reference

Auto-generated from `app.openapi()` (Housing Society Management API) — 160 endpoints across 24 modules. Regenerate with `python -m scripts.generate_api_reference` instead of hand-editing when endpoints change (see CLAUDE.md Section 8); the source of truth is always the live OpenAPI schema, not this file.

All endpoints are mounted under `/api/v1` and require a Bearer JWT (`Authorization: Bearer <token>`) unless noted otherwise — see `app/core/security.py`'s `require_role()` for the exact role check on each one. Interactive docs (Swagger UI) are available at `/docs` when the server is running.

## account-entries

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/account-entries` | List All |
| POST | `/api/v1/account-entries` | Create |
| GET | `/api/v1/account-entries/balance` | Balance |
| GET | `/api/v1/account-entries/headings` | List Headings |
| POST | `/api/v1/account-entries/headings` | Add Heading |
| PATCH | `/api/v1/account-entries/headings/{heading_id}` | Edit Heading |
| GET | `/api/v1/account-entries/pending-expense-bills` | Pending Expense Bills |
| POST | `/api/v1/account-entries/settle-expense-bill` | Settle Expense Bill |
| PATCH | `/api/v1/account-entries/{entry_id}` | Edit |

## admin-change

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/admin-change-requests` | List All |
| POST | `/api/v1/admin-change-requests` | Create |
| GET | `/api/v1/admin-change-requests/candidates` | Change Admin Candidates |
| GET | `/api/v1/admin-change-requests/history` | History |
| GET | `/api/v1/admin-change-requests/pending-for-me` | Pending For Me |
| POST | `/api/v1/admin-change-requests/resign` | Resign |
| GET | `/api/v1/admin-change-requests/resignation-candidates` | Resignation Candidates |
| POST | `/api/v1/admin-change-requests/{request_id}/decision` | Decide |

## admins

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/admins/pending` | List Pending |
| POST | `/api/v1/admins/signup` | Signup |
| POST | `/api/v1/admins/{admin_id}/approval` | Decide Approval |

## amenities

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/amenities` | List Amenities |
| POST | `/api/v1/amenities` | Create Amenity |
| GET | `/api/v1/amenities/bookings` | List Bookings |
| POST | `/api/v1/amenities/bookings` | Create Booking |
| POST | `/api/v1/amenities/bookings/{booking_id}/decision` | Decide Booking |
| GET | `/api/v1/amenities/{amenity_id}/slots` | Get Occupied Slots |

## auth

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/auth/logout` | Logout Endpoint |
| GET | `/api/v1/auth/me` | Get Me |
| POST | `/api/v1/auth/otp/request` | Request Otp Endpoint |
| POST | `/api/v1/auth/otp/verify` | Verify Otp Endpoint |
| POST | `/api/v1/auth/select-account` | Select Account Endpoint |
| POST | `/api/v1/auth/switch-role` | Switch Role Endpoint |
| POST | `/api/v1/auth/token/refresh` | Refresh Token Endpoint |

## complaints

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/complaints` | List All |
| POST | `/api/v1/complaints` | Create |
| POST | `/api/v1/complaints/{complaint_id}/assign` | Assign |
| POST | `/api/v1/complaints/{complaint_id}/rating` | Rate |
| PATCH | `/api/v1/complaints/{complaint_id}/status` | Update Status |

## expense-bills

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/expense-bills` | List All |
| POST | `/api/v1/expense-bills` | Create And Finalize |
| POST | `/api/v1/expense-bills/draft` | Create Draft |
| GET | `/api/v1/expense-bills/{bill_id}` | Get Detail |
| POST | `/api/v1/expense-bills/{bill_id}/decision` | Decide |
| POST | `/api/v1/expense-bills/{bill_id}/finalize` | Finalize |
| GET | `/api/v1/expense-bills/{bill_id}/image` | Get Bill Image |

## manager-todos

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/manager-todos` | List Todos |
| POST | `/api/v1/manager-todos` | Assign Todo |
| PATCH | `/api/v1/manager-todos/{todo_id}/status` | Update Status |
| GET | `/api/v1/managers/{manager_id}/daily-tasks` | List Daily Tasks |
| PUT | `/api/v1/managers/{manager_id}/daily-tasks` | Set Daily Tasks |
| GET | `/api/v1/task-suggestions` | List Task Suggestions |
| POST | `/api/v1/task-suggestions` | Add Task Suggestion |

## notices

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/notices` | List All |
| POST | `/api/v1/notices` | Create |

## notifications

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/notifications/mark-all-read` | Mark All Read |
| GET | `/api/v1/notifications/mine` | List Mine |
| GET | `/api/v1/notifications/unread-count` | Unread Count |
| PATCH | `/api/v1/notifications/{notification_id}/read` | Mark Read |

## payments

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/payments` | List Payments |
| POST | `/api/v1/payments` | Submit Payment |
| GET | `/api/v1/payments/maintenance-dues` | List Dues |
| GET | `/api/v1/payments/maintenance-dues/by-location/{location_id}` | List Outstanding Dues By Location |
| GET | `/api/v1/payments/maintenance-dues/by-property/{property_id}` | List Dues For Property |
| POST | `/api/v1/payments/maintenance-dues/generate` | Generate Bills |
| POST | `/api/v1/payments/maintenance-dues/{due_id}/waive-penalty` | Waive Penalty |
| GET | `/api/v1/payments/pending` | List Pending |
| GET | `/api/v1/payments/wallet/me` | My Wallet |
| POST | `/api/v1/payments/{payment_id}/approve` | Approve |
| POST | `/api/v1/payments/{payment_id}/correct` | Correct |
| GET | `/api/v1/payments/{payment_id}/proofs` | List Proofs |
| GET | `/api/v1/payments/{payment_id}/proofs/{proof_id}/file` | Get Proof File |
| POST | `/api/v1/payments/{payment_id}/reject` | Reject |

## properties

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/properties` | List Properties |
| POST | `/api/v1/properties` | Create Property |
| GET | `/api/v1/properties/locations` | List Locations |
| POST | `/api/v1/properties/locations` | Create Location |
| PATCH | `/api/v1/properties/{property_id}/status` | Update Property Status |

## proposals

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/proposals` | List All |
| POST | `/api/v1/proposals` | Create |
| GET | `/api/v1/proposals/{proposal_id}` | Get Detail |
| GET | `/api/v1/proposals/{proposal_id}/history` | Get Vote History |
| POST | `/api/v1/proposals/{proposal_id}/vote` | Vote |
| POST | `/api/v1/proposals/{proposal_id}/withdraw` | Withdraw |

## reports

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/reports/maintenance-summary` | Maintenance Summary |
| GET | `/api/v1/reports/manager-performance` | Manager Performance |
| GET | `/api/v1/reports/platform/{society_id}/balance` | Platform Balance |
| GET | `/api/v1/reports/platform/{society_id}/maintenance-summary` | Platform Maintenance Summary |
| GET | `/api/v1/reports/platform/{society_id}/manager-performance` | Platform Manager Performance |
| GET | `/api/v1/reports/platform/{society_id}/overview` | Platform Society Overview |
| GET | `/api/v1/reports/rateable-complaints` | Rateable Complaints |

## residents

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/residents` | List All |
| GET | `/api/v1/residents/by-location/{location_id}` | List By Location |
| GET | `/api/v1/residents/by-property/{property_id}` | Get Property Residents |
| GET | `/api/v1/residents/pending` | List Pending |
| POST | `/api/v1/residents/property-link-requests` | Request Property Link |
| GET | `/api/v1/residents/property-link-requests/mine` | My Property Link Requests |
| GET | `/api/v1/residents/property-link-requests/pending` | Pending Property Link Requests |
| POST | `/api/v1/residents/property-link-requests/{request_id}/decision` | Decide Property Link Request |
| POST | `/api/v1/residents/property-links` | Link Property |
| DELETE | `/api/v1/residents/property-links/{link_id}` | Unlink Property |
| PATCH | `/api/v1/residents/property-links/{link_id}/owner-contact` | Update Owner Contact |
| POST | `/api/v1/residents/self-link` | Link Self |
| POST | `/api/v1/residents/signup` | Signup |
| POST | `/api/v1/residents/{resident_id}/approval` | Decide Approval |
| GET | `/api/v1/residents/{resident_id}/properties` | Get Resident Properties |

## showcase-prefill

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/showcase-prefill` | Create Prefill Token |
| POST | `/api/v1/showcase-prefill/redeem` | Redeem Prefill Token |

## societies

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/societies` | List All |
| POST | `/api/v1/societies` | Create |
| GET | `/api/v1/societies/lookup/{code}` | Lookup |
| GET | `/api/v1/societies/me` | My Society |
| GET | `/api/v1/societies/reports` | List Reports |
| GET | `/api/v1/societies/search` | Search |
| POST | `/api/v1/societies/signup` | Signup |
| PATCH | `/api/v1/societies/{society_id}` | Update Profile |
| POST | `/api/v1/societies/{society_id}/approve` | Approve |
| GET | `/api/v1/societies/{society_id}/locations` | List Locations |
| POST | `/api/v1/societies/{society_id}/locations` | Add Location |
| GET | `/api/v1/societies/{society_id}/locations/public` | List Locations Public |
| DELETE | `/api/v1/societies/{society_id}/locations/{location_id}` | Delete Location |
| PATCH | `/api/v1/societies/{society_id}/locations/{location_id}` | Update Location |
| GET | `/api/v1/societies/{society_id}/properties` | List Society Properties |
| POST | `/api/v1/societies/{society_id}/properties` | Add Society Property |
| GET | `/api/v1/societies/{society_id}/properties/public` | List Properties Public |
| DELETE | `/api/v1/societies/{society_id}/properties/{property_id}` | Delete Society Property |
| PATCH | `/api/v1/societies/{society_id}/properties/{property_id}` | Edit Society Property |
| PATCH | `/api/v1/societies/{society_id}/properties/{property_id}/floors` | Update Property Floors |
| PATCH | `/api/v1/societies/{society_id}/status` | Update Status |
| POST | `/api/v1/societies/{society_id}/structure/bungalows` | Generate Bungalow Structure |
| POST | `/api/v1/societies/{society_id}/structure/flats` | Generate Flats Structure |

## staff

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/staff` | List Staff |
| POST | `/api/v1/staff` | Create Staff |
| DELETE | `/api/v1/staff/{user_id}` | Remove Staff |

## subadmins

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/subadmins` | List All |
| POST | `/api/v1/subadmins/promote` | Promote |
| POST | `/api/v1/subadmins/resignation` | Submit Resignation |
| GET | `/api/v1/subadmins/resignations/pending` | List Pending Resignations |
| POST | `/api/v1/subadmins/resignations/{request_id}/decision` | Decide Resignation |
| DELETE | `/api/v1/subadmins/scopes/{scope_id}` | Revoke Scope |
| DELETE | `/api/v1/subadmins/{sub_admin_id}` | Demote |
| GET | `/api/v1/subadmins/{sub_admin_id}/scopes` | List Scopes |
| POST | `/api/v1/subadmins/{sub_admin_id}/scopes` | Assign Scope |

## untagged

| Method | Path | Summary |
|---|---|---|
| GET | `/health` | Health |

## uploads

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/uploads/expense-bill-image` | Upload Expense Bill Image |
| POST | `/api/v1/uploads/payment-proof` | Upload Payment Proof |

## users

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/users/me` | Get My Profile |
| PATCH | `/api/v1/users/me` | Update My Profile |
| DELETE | `/api/v1/users/me/avatar` | Delete My Avatar |
| GET | `/api/v1/users/me/avatar` | Get My Avatar |
| POST | `/api/v1/users/me/avatar` | Upload My Avatar |

## visitors

| Method | Path | Summary |
|---|---|---|
| GET | `/api/v1/visitors` | List All |
| POST | `/api/v1/visitors` | Pre Approve |
| GET | `/api/v1/visitors/guard-view` | Guard View |
| GET | `/api/v1/visitors/mine` | My Visitors |
| POST | `/api/v1/visitors/{visitor_id}/entry` | Guard Mark Entry |
| POST | `/api/v1/visitors/{visitor_id}/exit` | Guard Mark Exit |
| PATCH | `/api/v1/visitors/{visitor_id}/status` | Resident Update Status |

## wallet-redemptions

| Method | Path | Summary |
|---|---|---|
| POST | `/api/v1/wallet-redemptions` | Create Redemption |
| GET | `/api/v1/wallet-redemptions/mine` | List My Redemptions |
| POST | `/api/v1/wallet-redemptions/verify` | Verify Redemption |
