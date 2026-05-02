import { useState, useEffect } from 'react';
import { CreditCard, CheckCircle, XCircle, Clock, FileText, ClipboardCheck, Wallet } from 'lucide-react';
import { maintenanceAPI, subAdminAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const SubAdminDashboard = () => {
  const { user } = useAuthStore();
  const [pendingPayments, setPendingPayments] = useState([]);
  const [pendingPlans, setPendingPlans] = useState([]);
  const [pendingExpenses, setPendingExpenses] = useState([]);
  const [wallet, setWallet] = useState({ balance: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [paymentsRes, plansRes, expensesRes, walletRes] = await Promise.all([
          maintenanceAPI.getPendingPayments(),
          subAdminAPI.getPendingPlans(),
          subAdminAPI.getPendingExpenses(),
          maintenanceAPI.getWallet(),
        ]);
        setPendingPayments(paymentsRes.data);
        setPendingPlans(plansRes.data);
        setPendingExpenses(expensesRes.data);
        setWallet(walletRes.data);
      } catch (e) {
        console.error('Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-bg-surface rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  const statCards = [
    { label: 'Pending Payments', value: pendingPayments.length, icon: CreditCard, color: 'text-warning' },
    { label: 'Pending Plans', value: pendingPlans.length, icon: ClipboardCheck, color: 'text-info' },
    { label: 'Pending Expenses', value: pendingExpenses.length, icon: FileText, color: 'text-accent' },
    { label: 'Wallet Points', value: wallet.balance, icon: Wallet, color: 'text-success' },
  ];

  return (
    <div data-testid="subadmin-dashboard" className="space-y-8">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Sub-Admin Dashboard</h1>
        <p className="text-text-secondary mt-1">Welcome back, {user?.name}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, i) => (
          <div key={i} className="card p-6">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-text-secondary text-sm">{stat.label}</p>
                <p className="text-3xl font-bold text-text-primary mt-2">{stat.value}</p>
              </div>
              <div className={`p-3 rounded-lg bg-bg-elevated ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const VerifyPayments = () => {
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedPayment, setSelectedPayment] = useState(null);
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const fetchPayments = async () => {
    try {
      const res = await maintenanceAPI.getPendingPayments();
      setPayments(res.data);
    } catch (e) {
      toast.error('Failed to load payments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, []);

  const handleApprove = async (billId) => {
    setProcessing(true);
    try {
      await maintenanceAPI.verifyPayment(billId, 'approve');
      toast.success('Payment verified and wallet credited');
      fetchPayments();
    } catch (e) {
      toast.error('Failed to verify payment');
    } finally {
      setProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast.error('Please enter a reason');
      return;
    }
    
    setProcessing(true);
    try {
      await maintenanceAPI.verifyPayment(selectedPayment.id, 'reject', rejectReason);
      toast.success('Payment rejected');
      setShowRejectModal(false);
      setSelectedPayment(null);
      setRejectReason('');
      fetchPayments();
    } catch (e) {
      toast.error('Failed to reject payment');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="verify-payments-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Verify Payments</h1>
        <p className="text-text-secondary mt-1">Review and verify pending payments in your wing</p>
      </div>

      <div className="card overflow-hidden">
        <div className="table-mobile-wrapper">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-3 sm:p-4">Flat</th>
                <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Resident</th>
                <th className="text-left p-3 sm:p-4">Month</th>
                <th className="text-left p-3 sm:p-4">Amount</th>
                <th className="text-left p-3 sm:p-4 hidden md:table-cell">Payment</th>
                <th className="text-left p-3 sm:p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {payments.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-text-secondary">
                    <CreditCard className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No pending payments to verify</p>
                  </td>
                </tr>
              ) : (
                payments.map((payment) => (
                  <tr key={payment.id} className="table-row">
                    <td className="p-3 sm:p-4 font-medium text-text-primary text-sm">{payment.flat_number}</td>
                    <td className="p-3 sm:p-4 text-text-primary text-sm hidden sm:table-cell">{payment.resident_name || '-'}</td>
                    <td className="p-3 sm:p-4 text-text-primary text-sm">{payment.month}</td>
                    <td className="p-3 sm:p-4 text-text-primary text-sm">{payment.amount}</td>
                    <td className="p-3 sm:p-4 text-text-secondary text-sm hidden md:table-cell">
                      <span className="badge-info">{payment.payment_mode?.toUpperCase()}</span>
                      <span className="ml-1 text-xs">{payment.payment_ref}</span>
                    </td>
                    <td className="p-3 sm:p-4">
                      <div className="flex gap-1.5">
                        <button
                          onClick={() => handleApprove(payment.id)}
                          disabled={processing}
                          data-testid={`approve-payment-${payment.id}`}
                          className="p-1.5 sm:p-2 bg-success/20 text-success rounded-lg hover:bg-success/30 transition-colors disabled:opacity-50"
                        >
                          <CheckCircle className="w-4 h-4 sm:w-5 sm:h-5" />
                        </button>
                        <button
                          onClick={() => {
                            setSelectedPayment(payment);
                            setShowRejectModal(true);
                          }}
                          disabled={processing}
                          data-testid={`reject-payment-${payment.id}`}
                          className="p-1.5 sm:p-2 bg-danger/20 text-danger rounded-lg hover:bg-danger/30 transition-colors disabled:opacity-50"
                        >
                          <XCircle className="w-4 h-4 sm:w-5 sm:h-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={showRejectModal} onOpenChange={setShowRejectModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Reject Payment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-bg-elevated rounded-lg">
              <p className="text-text-secondary text-sm">Payment for</p>
              <p className="text-text-primary font-medium">
                {selectedPayment?.flat_number} - {selectedPayment?.month}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Reason for Rejection
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                data-testid="reject-reason-input"
                className="input-field w-full min-h-[100px]"
                placeholder="Enter reason..."
                required
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowRejectModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={processing}
                data-testid="confirm-reject-btn"
                className="btn-danger disabled:opacity-50"
              >
                {processing ? 'Rejecting...' : 'Reject Payment'}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const PlanApprovals = () => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [decision, setDecision] = useState('approved');
  const [reason, setReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const fetchPlans = async () => {
    try {
      const res = await subAdminAPI.getPendingPlans();
      setPlans(res.data);
    } catch (e) {
      toast.error('Failed to load plans');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
  }, []);

  const handleSubmit = async () => {
    if (decision === 'rejected' && !reason.trim()) {
      toast.error('Please enter a reason for rejection');
      return;
    }
    
    setProcessing(true);
    try {
      await subAdminAPI.approvePlan(selectedPlan.plan.id, decision, reason);
      toast.success(`Plan ${decision}`);
      setShowModal(false);
      setSelectedPlan(null);
      setReason('');
      fetchPlans();
    } catch (e) {
      toast.error('Failed to process');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="plan-approvals-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Plan Approvals</h1>
        <p className="text-text-secondary mt-1">Review and approve society plans</p>
      </div>

      {plans.length === 0 ? (
        <div className="card p-12 text-center">
          <ClipboardCheck className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Pending Plans</h3>
          <p className="text-text-secondary">All plans have been reviewed</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {plans.map((item) => (
            <div key={item.approval_id} className="card p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-info/20 rounded-lg">
                  <ClipboardCheck className="w-6 h-6 text-info" />
                </div>
                <span className="badge-warning">Pending</span>
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">{item.plan.title}</h3>
              <p className="text-text-secondary mb-4">{item.plan.description}</p>
              {item.plan.amount && (
                <p className="text-accent font-semibold mb-4">
                  Estimated: ₹{item.plan.amount.toLocaleString()}
                </p>
              )}
              <button
                onClick={() => {
                  setSelectedPlan(item);
                  setShowModal(true);
                }}
                data-testid={`review-plan-${item.plan.id}`}
                className="btn-primary w-full"
              >
                Review & Decide
              </button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Review Plan</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-bg-elevated rounded-lg">
              <h3 className="font-semibold text-text-primary">{selectedPlan?.plan.title}</h3>
              <p className="text-text-secondary mt-2">{selectedPlan?.plan.description}</p>
              {selectedPlan?.plan.amount && (
                <p className="text-accent font-semibold mt-2">
                  ₹{selectedPlan?.plan.amount.toLocaleString()}
                </p>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Your Decision
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="decision"
                    value="approved"
                    checked={decision === 'approved'}
                    onChange={(e) => setDecision(e.target.value)}
                    className="text-success"
                  />
                  <span className="text-success">Approve</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="decision"
                    value="rejected"
                    checked={decision === 'rejected'}
                    onChange={(e) => setDecision(e.target.value)}
                    className="text-danger"
                  />
                  <span className="text-danger">Reject</span>
                </label>
              </div>
            </div>
            
            {decision === 'rejected' && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Reason for Rejection
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  data-testid="plan-reject-reason"
                  className="input-field w-full min-h-[100px]"
                  placeholder="Enter reason..."
                  required
                />
              </div>
            )}
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={processing}
                data-testid="submit-plan-decision"
                className={`${decision === 'approved' ? 'btn-primary' : 'btn-danger'} disabled:opacity-50`}
              >
                {processing ? 'Processing...' : decision === 'approved' ? 'Approve' : 'Reject'}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const ExpenseApprovals = () => {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedExpense, setSelectedExpense] = useState(null);
  const [decision, setDecision] = useState('approved');
  const [reason, setReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const fetchExpenses = async () => {
    try {
      const res = await subAdminAPI.getPendingExpenses();
      setExpenses(res.data);
    } catch (e) {
      toast.error('Failed to load expenses');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpenses();
  }, []);

  const handleSubmit = async () => {
    if (decision === 'rejected' && !reason.trim()) {
      toast.error('Please enter a reason for rejection');
      return;
    }
    
    setProcessing(true);
    try {
      await subAdminAPI.verifyExpense(selectedExpense.expense.id, decision, reason);
      toast.success(`Expense ${decision}`);
      setShowModal(false);
      setSelectedExpense(null);
      setReason('');
      fetchExpenses();
    } catch (e) {
      toast.error('Failed to process');
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="expense-approvals-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Expense Approvals</h1>
        <p className="text-text-secondary mt-1">Review and verify expense bills</p>
      </div>

      {expenses.length === 0 ? (
        <div className="card p-12 text-center">
          <FileText className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Pending Expenses</h3>
          <p className="text-text-secondary">All expenses have been reviewed</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {expenses.map((item) => (
            <div key={item.verification_id} className="card p-6">
              <div className="flex items-start justify-between mb-4">
                <span className="badge-info">{item.expense.category}</span>
                <span className="badge-warning">Pending</span>
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">{item.expense.title}</h3>
              <p className="text-text-secondary mb-2">{item.expense.description}</p>
              <p className="text-text-secondary text-sm mb-4">Date: {item.expense.bill_date}</p>
              <p className="text-2xl font-bold text-danger mb-4">
                ₹{item.expense.amount.toLocaleString()}
              </p>
              <button
                onClick={() => {
                  setSelectedExpense(item);
                  setShowModal(true);
                }}
                data-testid={`review-expense-${item.expense.id}`}
                className="btn-primary w-full"
              >
                Review & Decide
              </button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Review Expense</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-bg-elevated rounded-lg">
              <span className="badge-info mb-2">{selectedExpense?.expense.category}</span>
              <h3 className="font-semibold text-text-primary">{selectedExpense?.expense.title}</h3>
              <p className="text-text-secondary mt-2">{selectedExpense?.expense.description}</p>
              <p className="text-2xl font-bold text-danger mt-2">
                ₹{selectedExpense?.expense.amount.toLocaleString()}
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Your Decision
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="decision"
                    value="approved"
                    checked={decision === 'approved'}
                    onChange={(e) => setDecision(e.target.value)}
                  />
                  <span className="text-success">Approve</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="decision"
                    value="rejected"
                    checked={decision === 'rejected'}
                    onChange={(e) => setDecision(e.target.value)}
                  />
                  <span className="text-danger">Reject</span>
                </label>
              </div>
            </div>
            
            {decision === 'rejected' && (
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Reason for Rejection
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  data-testid="expense-reject-reason"
                  className="input-field w-full min-h-[100px]"
                  placeholder="Enter reason..."
                  required
                />
              </div>
            )}
            
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={processing}
                data-testid="submit-expense-decision"
                className={`${decision === 'approved' ? 'btn-primary' : 'btn-danger'} disabled:opacity-50`}
              >
                {processing ? 'Processing...' : decision === 'approved' ? 'Approve' : 'Reject'}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export { SubAdminDashboard, VerifyPayments, PlanApprovals, ExpenseApprovals };
