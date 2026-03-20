# Housing Society Management PWA - PRD

## Original Problem Statement
Full-stack PWA for Housing Society Management with 4 roles: Platform Owner, Admin, Sub-Admin, Resident. Features include: Auth, Society/Wing/Flat management, Maintenance bills, Wallet, Reports, Plans, Notices, Complaints.

## Architecture
- **Backend**: FastAPI + MongoDB (Pydantic models for validation)
- **Frontend**: React 19 + Tailwind CSS (custom dark navy theme)
- **Auth**: JWT with role-based access control, role-priority login
- **PWA**: Service Worker with network-first API, cache-first static

## User Personas
1. **Platform Owner**: Super admin - manages societies and admins
2. **Admin**: Society head - manages wings, flats, bills, residents, income, expenses, plans
3. **Sub-Admin**: Wing head - verifies payments, approves plans/expenses
4. **Resident**: Member - views/pays bills, wallet, reports, complaints

## Core Requirements
- 4 role-based dashboards with different permissions
- Wings and Flats CRUD with grid mapping
- Maintenance bill generation with preview
- Payment verification workflow
- Wallet system (₹1 = 1 point)
- Income/Expense/Outstanding reports
- Plan approval system (requires ALL sub-admins)
- Expense verification by sub-admins
- Notices and complaints

## What's Been Implemented - Jan 2026

### Phase 0+1 (Initial)
- [x] Complete backend API with all endpoints
- [x] JWT authentication with role-based guards
- [x] Platform Owner: Admin approval/block, shopping link
- [x] Admin: Wings CRUD, Bulk flat creation, Flat mapping grid
- [x] Maintenance bill generation with preview and exclusion
- [x] Reports: Income, Expense, Outstanding (RED text)
- [x] Notices CRUD, Complaints system
- [x] Dark navy theme (#0D1B2A) with orange accent (#E67E22)

### Phase 2 (Current)
- [x] Income Page - Add/view income entries with categories
- [x] Expenses Page - Add expense bills, sent to sub-admins for verification
- [x] Plans Page - Create plans requiring ALL sub-admin approvals
- [x] Sub-Admin verification flows for payments/expenses/plans
- [x] PWA manifest with proper theme colors
- [x] Service Worker with network-first for API, cache-first for static
- [x] Offline fallback page
- [x] Role-priority login (highest privilege role selected automatically)

## P0/P1 Features Remaining
- [ ] P1: End-to-end payment verification test (create resident, pay, verify)
- [ ] P1: Push notifications for payment status changes
- [ ] P2: File upload for expense receipts
- [ ] P2: Mobile responsive polish

## Demo Credentials
- Platform Owner: 9999999999 / owner123
- Admin: 8888888888 / admin123

## Next Tasks
1. Test end-to-end: Resident pays bill → Sub-Admin verifies → Wallet credited
2. Add push notification integration
3. File upload for expense receipts
