BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial_schema

CREATE TYPE society_status_enum AS ENUM ('PENDING', 'ACTIVE', 'SUSPENDED');

CREATE TYPE user_status_enum AS ENUM ('PENDING', 'ACTIVE', 'REJECTED', 'INACTIVE');

CREATE TYPE role_enum AS ENUM ('PLATFORM_OWNER', 'ADMIN', 'SUB_ADMIN', 'MANAGER', 'RESIDENT', 'SECURITY_GUARD');

CREATE TYPE location_type_enum AS ENUM ('WING', 'ROW');

CREATE TYPE house_type_enum AS ENUM ('FLAT', 'BUNGALOW');

CREATE TYPE relationship_type_enum AS ENUM ('OWNER', 'TENANT');

CREATE TYPE role_request_type_enum AS ENUM ('SUB_ADMIN_RESIGNATION');

CREATE TYPE role_request_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED');

CREATE TYPE maintenance_due_status_enum AS ENUM ('PENDING', 'PAID');

CREATE TYPE payment_method_enum AS ENUM ('MOCK_ONLINE', 'MANUAL_UPI', 'MANUAL_CASH');

CREATE TYPE payment_status_enum AS ENUM ('PENDING_APPROVAL', 'PAID', 'REJECTED');

CREATE TYPE proof_type_enum AS ENUM ('UPI_SCREENSHOT', 'CASH_RECEIPT');

CREATE TYPE payment_audit_action_enum AS ENUM ('CREATED', 'PAID_MARKED', 'APPROVED', 'REJECTED', 'CORRECTED');

CREATE TYPE wallet_txn_type_enum AS ENUM ('MAINTENANCE_CREDIT', 'ADJUSTMENT');

CREATE TYPE entry_type_enum AS ENUM ('INCOME', 'EXPENSE');

CREATE TYPE entry_source_enum AS ENUM ('MANUAL', 'MAINTENANCE_PAYMENT', 'EXPENSE_BILL', 'ADJUSTMENT');

CREATE TYPE todo_status_enum AS ENUM ('PENDING', 'IN_PROGRESS', 'DONE');

CREATE TYPE complaint_status_enum AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED');

CREATE TYPE visitor_status_enum AS ENUM ('PRE_APPROVED', 'EXPECTED', 'ENTERED', 'EXITED', 'CANCELLED');

CREATE TYPE booking_status_enum AS ENUM ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED');

CREATE TYPE proposal_scope_enum AS ENUM ('SOCIETY', 'WING', 'ROW');

CREATE TYPE proposal_status_enum AS ENUM ('OPEN', 'APPROVED', 'WITHDRAWN');

CREATE TYPE voter_role_enum AS ENUM ('RESIDENT', 'SUB_ADMIN');

CREATE TYPE vote_enum AS ENUM ('APPROVE', 'REJECT');

CREATE TYPE expense_bill_status_enum AS ENUM ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED');

CREATE TYPE decision_enum AS ENUM ('APPROVE', 'REJECT');

CREATE TYPE subscription_platform_enum AS ENUM ('WEB', 'ANDROID', 'IOS');

CREATE TABLE societies (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    status society_status_enum DEFAULT 'PENDING' NOT NULL, 
    address TEXT, 
    city VARCHAR(100), 
    state VARCHAR(100), 
    pincode VARCHAR(10), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID, 
    full_name VARCHAR(150) NOT NULL, 
    mobile VARCHAR(15) NOT NULL, 
    email VARCHAR(255), 
    status user_status_enum DEFAULT 'PENDING' NOT NULL, 
    created_by UUID, 
    approved_by UUID, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ux_users_society_id_id UNIQUE (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_users_society_mobile ON users (society_id, mobile) WHERE society_id IS NOT NULL;

CREATE UNIQUE INDEX ux_users_platform_owner_mobile ON users (mobile) WHERE society_id IS NULL;

CREATE TABLE user_roles (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    role role_enum NOT NULL, 
    assigned_by UUID, 
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_user_roles_active ON user_roles (user_id, role) WHERE revoked_at IS NULL;

CREATE TABLE society_locations (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    location_type location_type_enum NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ux_location_society_type_name UNIQUE (society_id, location_type, name), 
    CONSTRAINT ux_society_locations_society_id_id UNIQUE (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE properties (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    location_id UUID NOT NULL, 
    house_number VARCHAR(50) NOT NULL, 
    house_type house_type_enum NOT NULL, 
    floor_number INTEGER, 
    status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_properties_flat_requires_floor CHECK (house_type != 'FLAT' OR floor_number IS NOT NULL), 
    CONSTRAINT ux_properties_society_house UNIQUE (society_id, house_number), 
    CONSTRAINT ux_properties_society_id_id UNIQUE (society_id, id), 
    CONSTRAINT fk_properties_society_location FOREIGN KEY(society_id, location_id) REFERENCES society_locations (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE property_residents (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    resident_id UUID NOT NULL, 
    relationship_type relationship_type_enum NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    start_date DATE, 
    end_date DATE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_property_residents_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    CONSTRAINT fk_property_residents_society_resident FOREIGN KEY(society_id, resident_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE UNIQUE INDEX ux_property_residents_active ON property_residents (property_id, resident_id, relationship_type) WHERE is_active = true;

CREATE TABLE sub_admin_scopes (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    sub_admin_id UUID NOT NULL, 
    location_id UUID NOT NULL, 
    assigned_by UUID NOT NULL, 
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_sub_admin_scopes_society_subadmin FOREIGN KEY(society_id, sub_admin_id) REFERENCES users (society_id, id), 
    CONSTRAINT fk_sub_admin_scopes_society_location FOREIGN KEY(society_id, location_id) REFERENCES society_locations (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_sub_admin_scopes_active ON sub_admin_scopes (sub_admin_id, location_id) WHERE revoked_at IS NULL;

CREATE TABLE role_requests (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    society_id UUID NOT NULL, 
    request_type role_request_type_enum DEFAULT 'SUB_ADMIN_RESIGNATION' NOT NULL, 
    status role_request_status_enum DEFAULT 'PENDING' NOT NULL, 
    reason TEXT, 
    reviewed_by UUID, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    decision_reason TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_role_requests_society_user FOREIGN KEY(society_id, user_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(reviewed_by) REFERENCES users (id)
);

CREATE TABLE task_suggestions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    created_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE expense_bills (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT, 
    amount NUMERIC(12, 2) NOT NULL, 
    category VARCHAR(100), 
    status expense_bill_status_enum DEFAULT 'DRAFT' NOT NULL, 
    created_by UUID NOT NULL, 
    finalized_by UUID, 
    finalized_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_expense_bills_amount_positive CHECK (amount > 0), 
    CONSTRAINT ck_expense_bills_draft_no_finalizer CHECK (status != 'DRAFT' OR finalized_by IS NULL), 
    CONSTRAINT ux_expense_bills_society_id_id UNIQUE (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(finalized_by) REFERENCES users (id)
);

CREATE TABLE maintenance_dues (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    amount NUMERIC(12, 2) NOT NULL, 
    due_date DATE NOT NULL, 
    status maintenance_due_status_enum DEFAULT 'PENDING' NOT NULL, 
    billing_month DATE NOT NULL, 
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_maintenance_dues_amount_nonneg CHECK (amount >= 0), 
    CONSTRAINT ux_maintenance_due_month UNIQUE (society_id, property_id, billing_month), 
    CONSTRAINT ux_maintenance_dues_society_id_id UNIQUE (society_id, id), 
    CONSTRAINT fk_maintenance_dues_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE payments (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    maintenance_due_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    resident_id UUID NOT NULL, 
    payment_method payment_method_enum NOT NULL, 
    amount NUMERIC(12, 2) NOT NULL, 
    status payment_status_enum DEFAULT 'PENDING_APPROVAL' NOT NULL, 
    reference_number VARCHAR(150), 
    idempotency_key UUID NOT NULL, 
    paid_marked_at TIMESTAMP WITH TIME ZONE, 
    approved_at TIMESTAMP WITH TIME ZONE, 
    approved_by UUID, 
    rejected_at TIMESTAMP WITH TIME ZONE, 
    rejected_by UUID, 
    rejection_reason TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_payments_amount_positive CHECK (amount > 0), 
    CONSTRAINT ux_payments_due_idempotency UNIQUE (maintenance_due_id, idempotency_key), 
    CONSTRAINT fk_payments_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    CONSTRAINT fk_payments_society_resident FOREIGN KEY(society_id, resident_id) REFERENCES users (society_id, id), 
    CONSTRAINT fk_payments_society_due FOREIGN KEY(society_id, maintenance_due_id) REFERENCES maintenance_dues (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id), 
    FOREIGN KEY(rejected_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_payments_one_pending_per_due ON payments (maintenance_due_id) WHERE status = 'PENDING_APPROVAL';

CREATE TABLE account_entries (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    entry_type entry_type_enum NOT NULL, 
    source entry_source_enum NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT, 
    amount NUMERIC(12, 2) NOT NULL, 
    entry_date DATE NOT NULL, 
    is_edited BOOLEAN DEFAULT false NOT NULL, 
    last_edited_at TIMESTAMP WITH TIME ZONE, 
    related_payment_id UUID, 
    related_expense_bill_id UUID, 
    created_by UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_account_entries_amount_sign CHECK ((source IN ('MANUAL','MAINTENANCE_PAYMENT','EXPENSE_BILL') AND amount > 0) OR source = 'ADJUSTMENT'), 
    CONSTRAINT ck_account_entries_adjustment_is_income CHECK (source != 'ADJUSTMENT' OR entry_type = 'INCOME'), 
    CONSTRAINT ck_account_entries_maintenance_payment_shape CHECK (source != 'MAINTENANCE_PAYMENT' OR (entry_type = 'INCOME' AND related_payment_id IS NOT NULL AND related_expense_bill_id IS NULL)), 
    CONSTRAINT ck_account_entries_expense_bill_shape CHECK (source != 'EXPENSE_BILL' OR (entry_type = 'EXPENSE' AND related_expense_bill_id IS NOT NULL AND related_payment_id IS NULL)), 
    CONSTRAINT ck_account_entries_manual_shape CHECK (source != 'MANUAL' OR (related_payment_id IS NULL AND related_expense_bill_id IS NULL)), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(related_payment_id) REFERENCES payments (id), 
    FOREIGN KEY(related_expense_bill_id) REFERENCES expense_bills (id), 
    FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_account_entries_payment_once ON account_entries (related_payment_id) WHERE source = 'MAINTENANCE_PAYMENT';

CREATE UNIQUE INDEX ux_account_entries_expense_bill_once ON account_entries (related_expense_bill_id) WHERE source = 'EXPENSE_BILL';

CREATE TABLE payment_proofs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    payment_id UUID NOT NULL, 
    proof_type proof_type_enum NOT NULL, 
    file_url TEXT NOT NULL, 
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    uploaded_by UUID NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(payment_id) REFERENCES payments (id), 
    FOREIGN KEY(uploaded_by) REFERENCES users (id)
);

CREATE TABLE payment_audit_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    payment_id UUID NOT NULL, 
    action payment_audit_action_enum NOT NULL, 
    old_status VARCHAR(50), 
    new_status VARCHAR(50), 
    old_amount NUMERIC(12, 2), 
    new_amount NUMERIC(12, 2), 
    reason TEXT, 
    performed_by UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(payment_id) REFERENCES payments (id), 
    FOREIGN KEY(performed_by) REFERENCES users (id)
);

CREATE TABLE wallets (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    resident_id UUID NOT NULL, 
    balance NUMERIC(14, 2) DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_wallets_balance_nonneg CHECK (balance >= 0), 
    UNIQUE (resident_id), 
    FOREIGN KEY(resident_id) REFERENCES users (id)
);

CREATE TABLE wallet_transactions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    wallet_id UUID NOT NULL, 
    transaction_type wallet_txn_type_enum NOT NULL, 
    amount NUMERIC(14, 2) NOT NULL, 
    payment_id UUID, 
    description TEXT, 
    created_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(wallet_id) REFERENCES wallets (id), 
    FOREIGN KEY(payment_id) REFERENCES payments (id), 
    FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_wallet_txn_maintenance_credit_once ON wallet_transactions (wallet_id, payment_id, transaction_type) WHERE transaction_type = 'MAINTENANCE_CREDIT';

CREATE TABLE payment_corrections (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    payment_id UUID NOT NULL, 
    old_amount NUMERIC(12, 2) NOT NULL, 
    new_amount NUMERIC(12, 2) NOT NULL, 
    difference NUMERIC(12, 2) NOT NULL, 
    reason TEXT NOT NULL, 
    corrected_by UUID NOT NULL, 
    corrected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    wallet_adjustment_txn_id UUID, 
    ledger_adjustment_entry_id UUID, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_payment_corrections_diff CHECK (difference = new_amount - old_amount), 
    FOREIGN KEY(payment_id) REFERENCES payments (id), 
    FOREIGN KEY(corrected_by) REFERENCES users (id), 
    FOREIGN KEY(wallet_adjustment_txn_id) REFERENCES wallet_transactions (id), 
    FOREIGN KEY(ledger_adjustment_entry_id) REFERENCES account_entries (id)
);

CREATE UNIQUE INDEX ux_payment_corrections_wallet_txn ON payment_corrections (wallet_adjustment_txn_id) WHERE wallet_adjustment_txn_id IS NOT NULL;

CREATE UNIQUE INDEX ux_payment_corrections_ledger_entry ON payment_corrections (ledger_adjustment_entry_id) WHERE ledger_adjustment_entry_id IS NOT NULL;

CREATE TABLE account_entry_edit_history (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    account_entry_id UUID NOT NULL, 
    previous_title VARCHAR(200), 
    previous_description TEXT, 
    previous_amount NUMERIC(12, 2), 
    previous_entry_date DATE, 
    edited_by UUID NOT NULL, 
    edited_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(account_entry_id) REFERENCES account_entries (id), 
    FOREIGN KEY(edited_by) REFERENCES users (id)
);

CREATE TABLE manager_todos (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    manager_id UUID NOT NULL, 
    task_suggestion_id UUID NOT NULL, 
    task_date DATE NOT NULL, 
    status todo_status_enum DEFAULT 'PENDING' NOT NULL, 
    assigned_by UUID NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_manager_todos_society_manager FOREIGN KEY(society_id, manager_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(task_suggestion_id) REFERENCES task_suggestions (id), 
    FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE TABLE complaints (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    resident_id UUID NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    status complaint_status_enum DEFAULT 'OPEN' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_complaints_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    CONSTRAINT fk_complaints_society_resident FOREIGN KEY(society_id, resident_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE complaint_assignments (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    complaint_id UUID NOT NULL, 
    assigned_to UUID NOT NULL, 
    assigned_by UUID NOT NULL, 
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(complaint_id) REFERENCES complaints (id), 
    FOREIGN KEY(assigned_to) REFERENCES users (id), 
    FOREIGN KEY(assigned_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_complaint_assignments_current ON complaint_assignments (complaint_id) WHERE completed_at IS NULL;

CREATE TABLE visitors (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    resident_id UUID NOT NULL, 
    visitor_name VARCHAR(150) NOT NULL, 
    visitor_mobile VARCHAR(15), 
    visit_date DATE NOT NULL, 
    status visitor_status_enum DEFAULT 'PRE_APPROVED' NOT NULL, 
    purpose VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT fk_visitors_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    CONSTRAINT fk_visitors_society_resident FOREIGN KEY(society_id, resident_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE visitor_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    visitor_id UUID NOT NULL, 
    guard_id UUID NOT NULL, 
    entry_at TIMESTAMP WITH TIME ZONE, 
    exit_at TIMESTAMP WITH TIME ZONE, 
    notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(visitor_id) REFERENCES visitors (id), 
    FOREIGN KEY(guard_id) REFERENCES users (id)
);

CREATE TABLE notices (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    title VARCHAR(200) NOT NULL, 
    content TEXT NOT NULL, 
    created_by UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE amenities (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    description TEXT, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ux_amenities_society_id_id UNIQUE (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE amenity_bookings (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    amenity_id UUID NOT NULL, 
    property_id UUID NOT NULL, 
    resident_id UUID NOT NULL, 
    booking_date DATE NOT NULL, 
    start_time TIME WITHOUT TIME ZONE NOT NULL, 
    end_time TIME WITHOUT TIME ZONE NOT NULL, 
    status booking_status_enum DEFAULT 'PENDING' NOT NULL, 
    approved_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_amenity_bookings_time_range CHECK (start_time < end_time), 
    CONSTRAINT fk_amenity_bookings_society_amenity FOREIGN KEY(society_id, amenity_id) REFERENCES amenities (society_id, id), 
    CONSTRAINT fk_amenity_bookings_society_property FOREIGN KEY(society_id, property_id) REFERENCES properties (society_id, id), 
    CONSTRAINT fk_amenity_bookings_society_resident FOREIGN KEY(society_id, resident_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(approved_by) REFERENCES users (id)
);

CREATE TABLE proposals (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    scope_type proposal_scope_enum NOT NULL, 
    scope_location_id UUID, 
    title VARCHAR(200) NOT NULL, 
    description TEXT NOT NULL, 
    status proposal_status_enum DEFAULT 'OPEN' NOT NULL, 
    created_by UUID NOT NULL, 
    withdrawn_at TIMESTAMP WITH TIME ZONE, 
    withdrawn_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_proposals_scope_location_shape CHECK ((scope_type = 'SOCIETY' AND scope_location_id IS NULL) OR (scope_type IN ('WING','ROW') AND scope_location_id IS NOT NULL)), 
    CONSTRAINT fk_proposals_society_scope_location FOREIGN KEY(society_id, scope_location_id) REFERENCES society_locations (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(withdrawn_by) REFERENCES users (id)
);

CREATE TABLE proposal_votes (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    proposal_id UUID NOT NULL, 
    voter_id UUID NOT NULL, 
    voter_role voter_role_enum NOT NULL, 
    vote vote_enum NOT NULL, 
    voted_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ux_proposal_votes_one_per_voter UNIQUE (proposal_id, voter_id), 
    FOREIGN KEY(proposal_id) REFERENCES proposals (id), 
    FOREIGN KEY(voter_id) REFERENCES users (id)
);

CREATE TABLE proposal_vote_history (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    proposal_id UUID NOT NULL, 
    voter_id UUID NOT NULL, 
    old_vote vote_enum, 
    new_vote vote_enum NOT NULL, 
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(proposal_id) REFERENCES proposals (id), 
    FOREIGN KEY(voter_id) REFERENCES users (id)
);

CREATE TABLE expense_bill_approvals (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    society_id UUID NOT NULL, 
    expense_bill_id UUID NOT NULL, 
    sub_admin_id UUID NOT NULL, 
    decision decision_enum NOT NULL, 
    reason TEXT, 
    decided_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ux_expense_bill_approvals_once UNIQUE (expense_bill_id, sub_admin_id), 
    CONSTRAINT fk_expense_bill_approvals_society_bill FOREIGN KEY(society_id, expense_bill_id) REFERENCES expense_bills (society_id, id), 
    CONSTRAINT fk_expense_bill_approvals_society_subadmin FOREIGN KEY(society_id, sub_admin_id) REFERENCES users (society_id, id), 
    FOREIGN KEY(society_id) REFERENCES societies (id)
);

CREATE TABLE push_subscriptions (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    user_id UUID NOT NULL, 
    subscription_data TEXT NOT NULL, 
    platform subscription_platform_enum NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE UNIQUE INDEX ux_push_subscriptions_active ON push_subscriptions (user_id, subscription_data) WHERE revoked_at IS NULL;

INSERT INTO alembic_version (version_num) VALUES ('0001_initial_schema') RETURNING alembic_version.version_num;

COMMIT;

