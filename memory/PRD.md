# Housing Society Management PWA - PRD

## Original Problem Statement
Full-stack PWA for Housing Society Management with 4 roles: Platform Owner, Admin, Sub-Admin, Resident. Features include: Auth, Society/Wing/Flat management, Maintenance bills, Wallet, Reports, Plans, Notices, Complaints.

## Architecture
- **Backend**: FastAPI + MongoDB (Pydantic models for validation)
- **Frontend**: React 19 + Tailwind CSS (custom dark navy theme)
- **Auth**: JWT with role-based access control, OTP-based resident signup
- **PWA**: Service Worker with network-first API, cache-first static

## User Personas
1. **Platform Owner**: Super admin - manages societies, admins, bazaar settings
2. **Admin**: Society head - manages wings, flats, bills, residents, income, expenses, plans
3. **Sub-Admin**: Wing head - verifies payments, approves plans/expenses
4. **Resident**: Member - views/pays bills, wallet, reports, complaints, redeems points

## Core Requirements
- 4 role-based dashboards with different permissions
- Wings and Flats CRUD with grid mapping
- Maintenance bill generation with preview
- Payment verification workflow
- Wallet system (1 = 1 point) with Bazaar redemption
- Income/Expense/Outstanding reports
- Plan approval system (requires ALL sub-admins)
- Expense verification by sub-admins
- Notices and complaints

## What's Been Implemented

### Phase 0+1 (Initial) - Jan 2026
- [x] Complete backend API with all endpoints
- [x] JWT authentication with role-based guards
- [x] Platform Owner: Admin approval/block, shopping link
- [x] Admin: Wings CRUD, Bulk flat creation, Flat mapping grid
- [x] Maintenance bill generation with preview and exclusion
- [x] Reports: Income, Expense, Outstanding (RED text)
- [x] Notices CRUD, Complaints system
- [x] Dark navy theme (#0D1B2A) with orange accent (#E67E22)

### Phase 2 - Jan 2026
- [x] Income Page - Add/view income entries with categories
- [x] Expenses Page - Add expense bills, sent to sub-admins for verification
- [x] Plans Page - Create plans requiring ALL sub-admin approvals
- [x] Sub-Admin verification flows for payments/expenses/plans
- [x] PWA manifest with proper theme colors
- [x] Service Worker with network-first for API, cache-first for static
- [x] Offline fallback page
- [x] Role-priority login (highest privilege role selected automatically)

### Phase 3 - Mar 2026
- [x] **OTP-based Resident Signup**: Send OTP -> Verify -> Register (no password) -> Admin Approve -> Set Password -> Login
- [x] **Forgot Password Flow**: OTP verification -> Reset password
- [x] **Set Password Page**: For approved residents to create their login PIN/password
- [x] **OTP System**: 6-digit numeric, 5 min expiry, max 3 attempts, 10 min block (MOCKED - prints to console)
- [x] **Wallet + Bazaar Integration**: Platform Owner configures Bazaar API URL + Secret Key
- [x] **Bazaar Settings Page**: API URL, Secret Key, Connection Status indicator
- [x] **Wallet Redeem Feature**: Min 100 points, calls external Bazaar API, deducts only on success
- [x] **P0 Bug Fix**: resident_id properly linked to flat on admin approval and password setup
- [x] **Public API endpoints**: /societies, /wings, /flats for resident signup dropdowns
- [x] **Account Status Check**: API to check if account exists and needs password setup
- [x] **Platform Owner: Create Society** - Add Society with Admin in one go (name, address, location, admin details)
- [x] **Platform Owner: Society Location field** (June 2026) - society_location required in create form, shown on card
- [x] **Location GPS + Map Search** (June 2026) - LocationPicker component (OpenStreetMap Nominatim, no API key): current location detect via browser GPS + reverse geocode, search autocomplete (debounced, India-scoped). Saves address text + latitude/longitude in society doc. Used in both Add & Edit society dialogs.
- [x] **Platform Owner: Edit Society** (June 2026) - PUT /api/platform/societies/{id} (name/address/location) via edit dialog
- [x] **Platform Owner: Remove Society** (June 2026) - DELETE /api/platform/societies/{id} with AlertDialog confirm; cascades delete of users, wings, flats
- [x] **Mobile Responsive Polish** - All pages optimized for mobile: responsive headers (page-header), scrollable tabs, hidden columns on small screens, touch-friendly buttons, reduced padding

### Phase 4 - Feb 2026 (Design System overhaul)
- [x] **Phase A — CSS foundation**: Inter font, role-based CSS variables (`--accent`, `--accent-raw`, `--accent-light`), `.role-platform/.role-admin/.role-sub_admin/.role-resident/.role-manager` classes, flat shadow-free design, `.btn-*`, `.card`, `.stat-card`, `.input-field`, `.badge-*`, `.table-*`, `.sidebar-item`, `.topbar` component classes. Tailwind safelist for dynamic role classes.
- [x] **Phase B — Mobile + Components**:
  - Unified `RoleLayout.js` with desktop dark sidebar (240px) + 56px topbar
  - Mobile bottom navigation bar (64px, 4 items + More) with accent underline active state
  - Mobile drawer (hamburger) with full nav + role switch + logout
  - Mobile "More" sheet for overflow nav items
  - OTP input redesign (`OtpInput.js`) — 6 separate boxes, auto-advance, backspace, paste support
  - Stat cards migrated to `.stat-card` with role-accent 3px left border on all dashboards
  - Toaster theme switched dark → light
- [x] **Phase C — Feature-specific screens**:
  - **Notice Board** redesign — pinned section with accent left-border, time-ago metadata, mobile FAB (`create-notice-fab`), polished empty state, accent-light pin checkbox
  - **Complaints** with filter chips (All/Open/In Progress/Resolved) + count badges, card-grid view, **detail dialog** (`complaint-detail`) with status update panel, mobile FAB
  - **Haat Bazaar** redesigned hero card (accent-light bg + decorative shopping bag), connection pill, balance pill, "Visit Bazaar" CTA, "How it works" 3-step section
  - **Resident My Bills** — outstanding-amount hero (red bg if pending), "Pay Next" CTA, grouped sections (Action required / Awaiting verification / Verified history collapsible), bill rows with receipt icon
  - **Admin Maintenance Bills** — batch chip selector, 4 summary stat-cards (Total/Verified/Awaiting/Pending), polished generate modal with 3 stat-cards in preview
  - DialogContent ARIA fix to suppress aria-describedby warning

## Demo Credentials
- Platform Owner: 9999999999 / owner123

## P0/P1 Features Remaining
- [ ] P1: Push notifications for payment status changes
- [ ] P1: File upload for expense receipts (backend ready, frontend integration pending)
- [ ] P1: Phase D polish — replace `window.prompt`/`window.confirm` with shadcn AlertDialog (cancel-bill reasons, delete confirmations)
- [ ] P2: Real SMS integration (Fast2SMS/MSG91) - currently MOCKED
- [ ] P2: Sub-Admin temporary password SMS on promotion
- [ ] P3: Admin as Resident dual-role switching

- Admin: 8888888888 / admin123
- Sub-Admin: 7777777777 / subadmin123
- Test Resident: 5555555550 / newpass123

## Auth Flow
### Resident Signup:
1. Enter Name, Mobile, Society, Wing, Flat
2. Send OTP -> Verify 6-digit OTP
3. Account created (status: pending)
4. Admin approves -> status: approved
5. Resident sets password -> status: active -> can login

### Login (All Roles):
Mobile + Password -> JWT -> Role-based redirect

### Forgot Password:
Mobile -> OTP -> Verify -> New Password -> Login

## Bazaar Integration
- Platform Owner sets Bazaar API URL + Secret Key in Settings
- Connection status shown (Connected/Not Connected)
- Residents see Redeem button on Wallet page when connected
- Minimum redeem: 100 points
- API call: POST {bazaar_url}/api/points/credit
- Points deducted ONLY after successful API response
- Transaction logged as debit in wallet_transactions

## MOCKED Features
- OTP SMS: Returns mock_otp in API response (no real SMS sent)
- Bazaar External API: Not a real service - redeem will fail with connection error

## PWA (June 2026)
- [x] PWA Install Fix: manifest.json uses PNG icons (72-512 sizes, purpose any + separate maskable 192/512), index.html has favicon-32.png + /icons/apple-touch-icon.png links, sw.js cache bumped to societyhub-v2 with icons pre-cached. SW registered & activated — install criteria verified in browser.
