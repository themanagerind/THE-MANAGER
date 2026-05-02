import { useState, useEffect } from 'react';
import { Receipt, CreditCard, Clock, CheckCircle, XCircle, IndianRupee, Wallet, ArrowUpRight, ShoppingBag } from 'lucide-react';
import { maintenanceAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const ResidentDashboard = () => {
  const { user } = useAuthStore();
  const [bills, setBills] = useState([]);
  const [wallet, setWallet] = useState({ balance: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [billsRes, walletRes] = await Promise.all([
          maintenanceAPI.getMyBills(),
          maintenanceAPI.getWallet(),
        ]);
        setBills(billsRes.data);
        setWallet(walletRes.data);
      } catch (e) {
        console.error('Failed to load data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const pendingBills = bills.filter(b => b.status === 'pending' || b.status === 'overdue');
  const totalPending = pendingBills.reduce((sum, b) => sum + b.amount, 0);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => <div key={i} className="h-32 bg-bg-surface rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="resident-dashboard" className="space-y-8">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Welcome, {user?.name}</h1>
        <p className="text-text-secondary mt-1">Your society dashboard</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-text-secondary text-sm">Pending Bills</p>
              <p className="text-3xl font-bold text-danger mt-2">{pendingBills.length}</p>
              <p className="text-danger text-sm mt-1">{totalPending.toLocaleString()} total</p>
            </div>
            <div className="p-3 rounded-lg bg-danger/20 text-danger"><Receipt className="w-6 h-6" /></div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-text-secondary text-sm">Wallet Balance</p>
              <p className="text-3xl font-bold text-success mt-2">{wallet.balance}</p>
              <p className="text-success text-sm mt-1">points</p>
            </div>
            <div className="p-3 rounded-lg bg-success/20 text-success"><Wallet className="w-6 h-6" /></div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-text-secondary text-sm">Total Paid</p>
              <p className="text-3xl font-bold text-info mt-2">{bills.filter(b => b.status === 'verified').length}</p>
              <p className="text-info text-sm mt-1">bills this year</p>
            </div>
            <div className="p-3 rounded-lg bg-info/20 text-info"><CheckCircle className="w-6 h-6" /></div>
          </div>
        </div>
      </div>
    </div>
  );
};

const MyBills = () => {
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPayModal, setShowPayModal] = useState(false);
  const [selectedBill, setSelectedBill] = useState(null);
  const [paymentForm, setPaymentForm] = useState({ mode: 'upi', ref: '' });
  const [paying, setPaying] = useState(false);

  const fetchBills = async () => {
    try {
      const res = await maintenanceAPI.getMyBills();
      setBills(res.data);
    } catch (e) {
      toast.error('Failed to load bills');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBills(); }, []);

  const handlePay = async (e) => {
    e.preventDefault();
    if (!selectedBill) return;
    setPaying(true);
    try {
      await maintenanceAPI.payBill(selectedBill.id, paymentForm.mode, paymentForm.ref);
      toast.success('Payment submitted! Waiting for verification.');
      setShowPayModal(false);
      setSelectedBill(null);
      setPaymentForm({ mode: 'upi', ref: '' });
      fetchBills();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to submit payment');
    } finally {
      setPaying(false);
    }
  };

  const getStatusBadge = (bill) => {
    switch (bill.status) {
      case 'verified': return <span className="badge-success">Verified</span>;
      case 'paid': return <span className="badge-info">Awaiting Verification</span>;
      case 'pending': return <span className="badge-warning">Pending</span>;
      case 'overdue': return <span className="badge-danger">Overdue</span>;
      default: return <span className="badge-info">{bill.status}</span>;
    }
  };

  if (loading) {
    return <div className="animate-pulse space-y-6"><div className="h-8 bg-bg-surface rounded w-48" /><div className="h-96 bg-bg-surface rounded-xl" /></div>;
  }

  return (
    <div data-testid="my-bills-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">My Bills</h1>
        <p className="text-text-secondary mt-1">View and pay your maintenance bills</p>
      </div>
      <div className="card overflow-hidden">
        <div className="table-mobile-wrapper">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-3 sm:p-4">Month</th>
                <th className="text-left p-3 sm:p-4">Amount</th>
                <th className="text-left p-3 sm:p-4">Status</th>
                <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Payment</th>
                <th className="text-left p-3 sm:p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bills.length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-text-secondary">
                  <Receipt className="w-12 h-12 mx-auto mb-2 opacity-50" /><p>No bills found</p>
                </td></tr>
              ) : bills.map((bill) => (
                <tr key={bill.id} className="table-row">
                  <td className="p-3 sm:p-4 font-medium text-text-primary text-sm">{bill.month}</td>
                  <td className="p-3 sm:p-4 text-text-primary text-sm">{bill.amount}</td>
                  <td className="p-3 sm:p-4">{getStatusBadge(bill)}</td>
                  <td className="p-3 sm:p-4 text-text-secondary text-sm hidden sm:table-cell">
                    {bill.payment_mode ? <span>{bill.payment_mode.toUpperCase()} - {bill.payment_ref}</span> : '-'}
                  </td>
                  <td className="p-3 sm:p-4">
                    {(bill.status === 'pending' || bill.status === 'overdue') && (
                      <button onClick={() => { setSelectedBill(bill); setShowPayModal(true); }}
                        data-testid={`pay-bill-${bill.id}`} className="btn-primary text-xs sm:text-sm py-1 px-2 sm:px-3">Pay Now</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={showPayModal} onOpenChange={setShowPayModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader><DialogTitle className="text-text-primary">Submit Payment</DialogTitle></DialogHeader>
          <div className="mb-4 p-4 bg-bg-elevated rounded-lg">
            <p className="text-text-secondary text-sm">Bill for</p>
            <p className="text-xl font-bold text-text-primary">{selectedBill?.month}</p>
            <p className="text-2xl font-bold text-accent">{selectedBill?.amount}</p>
          </div>
          <form onSubmit={handlePay} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Payment Mode</label>
              <select value={paymentForm.mode}
                onChange={(e) => setPaymentForm({ ...paymentForm, mode: e.target.value })}
                data-testid="payment-mode-select" className="input-field w-full">
                <option value="upi">UPI</option>
                <option value="cash">Cash</option>
                <option value="bank">Bank Transfer</option>
                <option value="cheque">Cheque</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Reference Number / Transaction ID</label>
              <input type="text" value={paymentForm.ref}
                onChange={(e) => setPaymentForm({ ...paymentForm, ref: e.target.value })}
                data-testid="payment-ref-input" className="input-field w-full" placeholder="Enter reference number" required />
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowPayModal(false)} className="btn-secondary">Cancel</button>
              <button type="submit" disabled={paying} data-testid="submit-payment-btn"
                className="btn-primary disabled:opacity-50">{paying ? 'Submitting...' : 'Submit Payment'}</button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const WalletPage = () => {
  const [wallet, setWallet] = useState({ balance: 0, transactions: [] });
  const [bazaarStatus, setBazaarStatus] = useState({ connected: false, shopping_link: null });
  const [loading, setLoading] = useState(true);
  const [showRedeemModal, setShowRedeemModal] = useState(false);
  const [redeemPoints, setRedeemPoints] = useState('');
  const [redeeming, setRedeeming] = useState(false);

  const fetchData = async () => {
    try {
      const [walletRes, bazaarRes] = await Promise.all([
        maintenanceAPI.getWallet(),
        maintenanceAPI.getBazaarStatus(),
      ]);
      setWallet(walletRes.data);
      setBazaarStatus(bazaarRes.data);
    } catch (e) {
      toast.error('Failed to load wallet');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRedeem = async () => {
    const pts = parseFloat(redeemPoints);
    if (isNaN(pts) || pts < 100) {
      toast.error('Minimum redeem amount is 100 points');
      return;
    }
    if (pts > wallet.balance) {
      toast.error('Insufficient balance');
      return;
    }
    setRedeeming(true);
    try {
      const res = await maintenanceAPI.redeemPoints(pts);
      toast.success(res.data.message);
      setShowRedeemModal(false);
      setRedeemPoints('');
      fetchData();
      // Redirect to bazaar
      if (res.data.redirect_url) {
        setTimeout(() => {
          window.open(res.data.redirect_url, '_blank');
        }, 1500);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Redeem failed. Points not deducted.');
    } finally {
      setRedeeming(false);
    }
  };

  if (loading) {
    return <div className="animate-pulse space-y-6"><div className="h-8 bg-bg-surface rounded w-48" /><div className="h-64 bg-bg-surface rounded-xl" /></div>;
  }

  return (
    <div data-testid="wallet-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">My Wallet</h1>
        <p className="text-text-secondary mt-1">Track your reward points</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl">
        {/* Balance Card */}
        <div className="card p-8">
          <div className="flex items-center gap-4 mb-6">
            <div className="p-4 bg-accent/20 rounded-xl">
              <Wallet className="w-10 h-10 text-accent" />
            </div>
            <div>
              <p className="text-text-secondary text-sm">Available Balance</p>
              <p className="text-4xl font-bold text-accent">{wallet.balance}</p>
              <p className="text-text-secondary text-sm">points</p>
            </div>
          </div>
          <p className="text-text-secondary text-sm mb-4">1 = 1 point. Points credited on payment verification.</p>

          {/* Redeem Button */}
          {bazaarStatus.connected ? (
            <button onClick={() => setShowRedeemModal(true)}
              data-testid="redeem-points-btn"
              disabled={wallet.balance < 100}
              className="btn-primary w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
              <ShoppingBag className="w-5 h-5" />
              {wallet.balance < 100 ? 'Min 100 points to redeem' : 'Redeem Points'}
            </button>
          ) : (
            <div className="p-3 bg-bg-elevated rounded-lg text-center">
              <p className="text-text-muted text-sm">Bazaar not connected yet</p>
              <p className="text-text-muted text-xs mt-1">Contact your platform admin to enable redemption</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card p-8">
          <h3 className="font-semibold text-text-primary mb-4">How Points Work</h3>
          <div className="space-y-3 text-sm text-text-secondary">
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-success/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-success text-xs font-bold">1</span>
              </div>
              <p>Pay your maintenance bill on time</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-info/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-info text-xs font-bold">2</span>
              </div>
              <p>Sub-Admin verifies your payment</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-accent text-xs font-bold">3</span>
              </div>
              <p>Points credited = bill amount (1 = 1 point)</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-6 h-6 rounded-full bg-warning/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-warning text-xs font-bold">4</span>
              </div>
              <p>Redeem points at the Bazaar for shopping!</p>
            </div>
          </div>
        </div>
      </div>

      {/* Transaction History */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-border-color">
          <h3 className="font-semibold text-text-primary">Transaction History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-4">Date</th>
                <th className="text-left p-4">Description</th>
                <th className="text-right p-4">Points</th>
                <th className="text-right p-4">Balance</th>
              </tr>
            </thead>
            <tbody>
              {wallet.transactions.length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-text-secondary">
                  <Wallet className="w-12 h-12 mx-auto mb-2 opacity-50" /><p>No transactions yet</p>
                </td></tr>
              ) : wallet.transactions.map((txn, i) => (
                <tr key={i} className="table-row">
                  <td className="p-4 text-text-secondary text-sm">{new Date(txn.created_at).toLocaleDateString()}</td>
                  <td className="p-4 text-text-primary">{txn.description}</td>
                  <td className={`p-4 text-right font-medium ${txn.type === 'credit' ? 'text-success' : 'text-danger'}`}>
                    {txn.type === 'credit' ? '+' : '-'}{txn.points}
                  </td>
                  <td className="p-4 text-right text-text-primary">{txn.balance_after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Redeem Modal */}
      <Dialog open={showRedeemModal} onOpenChange={setShowRedeemModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader><DialogTitle className="text-text-primary">Redeem Points</DialogTitle></DialogHeader>
          <div className="mb-4 p-4 bg-bg-elevated rounded-lg">
            <p className="text-text-secondary text-sm">Available Balance</p>
            <p className="text-3xl font-bold text-accent">{wallet.balance} points</p>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Points to Redeem</label>
              <input type="number" value={redeemPoints}
                onChange={(e) => setRedeemPoints(e.target.value)}
                data-testid="redeem-points-input"
                className="input-field w-full" placeholder="Min 100 points" min={100} max={wallet.balance} />
              <p className="text-text-muted text-xs mt-1">Minimum: 100 points | Maximum: {wallet.balance} points</p>
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowRedeemModal(false)} className="btn-secondary">Cancel</button>
              <button onClick={handleRedeem} disabled={redeeming}
                data-testid="confirm-redeem-btn"
                className="btn-primary disabled:opacity-50 flex items-center gap-2">
                {redeeming ? 'Processing...' : <><ArrowUpRight className="w-4 h-4" /> Confirm Redeem</>}
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export { ResidentDashboard, MyBills, WalletPage };
