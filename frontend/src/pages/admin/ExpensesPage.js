import { useState, useEffect } from 'react';
import { TrendingDown, Plus, FileText, CheckCircle, XCircle, Clock } from 'lucide-react';
import { adminAPI } from '../../lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const EXPENSE_CATEGORIES = [
  { value: 'repair', label: 'Repair' },
  { value: 'cleaning', label: 'Cleaning' },
  { value: 'security', label: 'Security' },
  { value: 'electricity', label: 'Electricity' },
  { value: 'water', label: 'Water' },
  { value: 'other', label: 'Other' },
];

const ExpensesPage = () => {
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    category: 'repair',
    amount: '',
    bill_date: new Date().toISOString().split('T')[0],
    description: '',
  });

  const fetchExpenses = async () => {
    try {
      const res = await adminAPI.getExpenses();
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminAPI.createExpense({
        ...formData,
        amount: parseFloat(formData.amount),
      });
      toast.success('Expense bill added and sent for verification');
      setShowModal(false);
      setFormData({
        title: '',
        category: 'repair',
        amount: '',
        bill_date: new Date().toISOString().split('T')[0],
        description: '',
      });
      fetchExpenses();
    } catch (e) {
      toast.error('Failed to add expense');
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'verified':
        return <span className="badge-success flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Verified</span>;
      case 'rejected':
        return <span className="badge-danger flex items-center gap-1"><XCircle className="w-3 h-3" /> Rejected</span>;
      case 'partially_verified':
        return <span className="badge-warning flex items-center gap-1"><Clock className="w-3 h-3" /> Partial</span>;
      default:
        return <span className="badge-warning flex items-center gap-1"><Clock className="w-3 h-3" /> Pending</span>;
    }
  };

  const totalExpenses = expenses.reduce((sum, e) => sum + e.amount, 0);
  const verifiedExpenses = expenses.filter(e => e.status === 'verified').reduce((sum, e) => sum + e.amount, 0);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="expenses-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Expenses</h1>
          <p className="text-text-secondary mt-1">Track and manage expense bills</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          data-testid="add-expense-btn"
          className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center"
        >
          <Plus className="w-5 h-5" />
          Add Expense
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-danger/20 rounded-xl">
              <TrendingDown className="w-6 h-6 text-danger" />
            </div>
            <div>
              <p className="text-text-secondary text-sm">Total Expenses</p>
              <p className="text-2xl font-bold text-danger">₹{totalExpenses.toLocaleString()}</p>
            </div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-success/20 rounded-xl">
              <CheckCircle className="w-6 h-6 text-success" />
            </div>
            <div>
              <p className="text-text-secondary text-sm">Verified Amount</p>
              <p className="text-2xl font-bold text-success">₹{verifiedExpenses.toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Expenses Table */}
      <div className="card overflow-hidden">
        <div className="table-mobile-wrapper">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Date</th>
                <th className="text-left p-3 sm:p-4">Title</th>
                <th className="text-left p-3 sm:p-4 hidden md:table-cell">Category</th>
                <th className="text-left p-3 sm:p-4">Status</th>
                <th className="text-left p-3 sm:p-4 hidden lg:table-cell">Verifications</th>
                <th className="text-right p-3 sm:p-4">Amount</th>
              </tr>
            </thead>
            <tbody>
              {expenses.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-text-secondary">
                    <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No expense bills yet</p>
                  </td>
                </tr>
              ) : (
                expenses.map((expense) => (
                  <tr key={expense.id} className="table-row">
                    <td className="p-3 sm:p-4 text-text-primary text-sm hidden sm:table-cell">{expense.bill_date}</td>
                    <td className="p-3 sm:p-4">
                      <div>
                        <p className="font-medium text-text-primary text-sm">{expense.title}</p>
                        {expense.description && (
                          <p className="text-xs text-text-secondary truncate max-w-[150px] sm:max-w-[200px]">
                            {expense.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="p-3 sm:p-4 hidden md:table-cell">
                      <span className="badge-info">
                        {EXPENSE_CATEGORIES.find(c => c.value === expense.category)?.label || expense.category}
                      </span>
                    </td>
                    <td className="p-3 sm:p-4">{getStatusBadge(expense.status)}</td>
                    <td className="p-3 sm:p-4 hidden lg:table-cell">
                      {expense.verifications?.length > 0 ? (
                        <div className="space-y-1">
                          {expense.verifications.map((v, i) => (
                            <div key={i} className="text-xs">
                              <span className={`${v.decision === 'approved' ? 'text-success' : v.decision === 'rejected' ? 'text-danger' : 'text-warning'}`}>
                                {v.sub_admin_name}: {v.decision}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-text-muted text-sm">Awaiting</span>
                      )}
                    </td>
                    <td className="p-3 sm:p-4 text-right font-semibold text-danger">
                      ₹{expense.amount.toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
            {expenses.length > 0 && (
              <tfoot className="bg-danger/10">
                <tr>
                  <td className="p-3 sm:p-4 hidden sm:table-cell"></td>
                  <td className="p-3 sm:p-4 font-bold text-text-primary">Grand Total</td>
                  <td className="p-3 sm:p-4 hidden md:table-cell"></td>
                  <td className="p-3 sm:p-4"></td>
                  <td className="p-3 sm:p-4 hidden lg:table-cell"></td>
                  <td className="p-3 sm:p-4 text-right font-bold text-danger text-lg">
                    ₹{totalExpenses.toLocaleString()}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>

      {/* Add Expense Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Add Expense Bill</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="expense-title-input"
                className="input-field w-full"
                placeholder="e.g., Elevator Repair"
                required
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Category
                </label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  data-testid="expense-category-select"
                  className="input-field w-full"
                >
                  {EXPENSE_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Bill Date
                </label>
                <input
                  type="date"
                  value={formData.bill_date}
                  onChange={(e) => setFormData({ ...formData, bill_date: e.target.value })}
                  data-testid="expense-date-input"
                  className="input-field w-full"
                  required
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Amount (₹)
              </label>
              <input
                type="number"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                data-testid="expense-amount-input"
                className="input-field w-full"
                placeholder="0"
                min="1"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Description (Optional)
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                data-testid="expense-description-input"
                className="input-field w-full min-h-[80px]"
                placeholder="Additional details about the expense..."
              />
            </div>
            
            <p className="text-text-secondary text-sm bg-bg-elevated p-3 rounded-lg">
              <strong>Note:</strong> This expense bill will be sent to all sub-admins for verification.
            </p>
            
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                data-testid="submit-expense-btn"
                className="btn-primary disabled:opacity-50"
              >
                {saving ? 'Adding...' : 'Add Expense'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ExpensesPage;
