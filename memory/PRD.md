# Housing Society Management PWA - PRD

## Original Problem Statement
Full-stack PWA for Housing Society Management with 4 roles: Platform Owner, Admin, Sub-Admin, Resident. Features include auth, society management, maintenance bills, wallet, reports.

## Architecture
- **Backend**: FastAPI + MongoDB (Pydantic models for validation)
- **Frontend**: React 19 + Tailwind CSS (custom dark navy theme)
- **Auth**: JWT with role-based access control

## User Personas
1. **Platform Owner**: Super admin - manages societies and admins
2. **Admin**: Society head - manages wings, flats, bills, residents
3. **Sub-Admin**: Wing head - verifies payments, approves plans
4. **Resident**: Member - views/pays bills, wallet, reports

## Core Requirements
- 4 role-based dashboards with different permissions
- Wings and Flats CRUD with grid mapping
- Maintenance bill generation with preview
- Payment verification workflow
- Wallet system (₹1 = 1 point)
- Income/Expense/Outstanding reports
- Plan approval system
- Notices and complaints

## What's Been Implemented (Phase 0+1) - Jan 2026
- [x] Complete backend API with all endpoints
- [x] JWT authentication with role-based guards
- [x] Platform Owner: Admin approval/block, shopping link
- [x] Admin: Wings CRUD, Bulk flat creation, Flat mapping grid
- [x] Maintenance bill generation with preview and exclusion
- [x] Reports: Income, Expense, Outstanding (RED text)
- [x] Notices CRUD, Complaints system
- [x] Dark navy theme (#0D1B2A) with orange accent (#E67E22)
- [x] Plus Jakarta Sans font

## P0/P1 Features Remaining
- [ ] P0: Resident payment flow (pay bill → sub-admin verify)
- [ ] P0: Sub-Admin payment verification UI
- [ ] P1: Income/Expense entry forms
- [ ] P1: Plan creation and approval flow
- [ ] P1: Wallet redemption (Bazaar)
- [ ] P2: PWA setup with service worker
- [ ] P2: Mobile responsive polish

## Demo Credentials
- Platform Owner: 9999999999 / owner123
- Test Admin: 8888888888 / admin123

## Next Tasks
1. Complete Sub-Admin payment verification flow
2. Add Income/Expense entry forms for Admin
3. Implement Plan approval workflow
4. Test end-to-end payment → wallet credit flow
