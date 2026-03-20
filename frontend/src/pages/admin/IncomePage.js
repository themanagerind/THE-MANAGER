import { useState, useEffect } from 'react';
import { TrendingUp, Plus, Calendar, IndianRupee, Trash2 } from 'lucide-react';
import { adminAPI } from '../../lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const INCOME_CATEGORIES = [
  { value: 'maintenance_collection', label: 'Maintenance Collection' },
  { value: 'scrape_sell', label: 'Scrape Sell' },
  { value: 'lawn_rent', label: 'Lawn Rent' },
  { value: 'parking_fee', label: 'Parking Fee' },
  { value: 'other', label: 'Other' },
];

const IncomePage = () => {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    category: 'maintenance_collection',
    amount: '',
    entry_date: new Date().toISOString().split('T')[0],
    description: '',
  });

  const fetchEntries = async () => {
    try {
      const res = await adminAPI.getIncome();
      setEntries(res.data);
    } catch (e) {
      toast.error('Failed to load income entries');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntries();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminAPI.createIncome({
        ...formData,
        amount: parseFloat(formData.amount),
      });
      toast.success('Income entry added');
      setShowModal(false);
      setFormData({
        title: '',
        category: 'maintenance_collection',
        amount: '',
        entry_date: new Date().toISOString().split('T')[0],
        description: '',
      });
      fetchEntries();
    } catch (e) {
      toast.error('Failed to add income entry');
    } finally {
      setSaving(false);
    }
  };

  const totalIncome = entries.reduce((sum, e) => sum + e.amount, 0);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="income-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Income</h1>
          <p className="text-text-secondary mt-1">Track society income</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          data-testid="add-income-btn"
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Add Income
        </button>
      </div>

      {/* Summary Card */}
      <div className="card p-6 max-w-sm">
        <div className="flex items-center gap-4">
          <div className="p-4 bg-success/20 rounded-xl">
            <TrendingUp className="w-8 h-8 text-success" />
          </div>
          <div>
            <p className="text-text-secondary text-sm">Total Income</p>
            <p className="text-3xl font-bold text-success">₹{totalIncome.toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Entries Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-4">Date</th>
                <th className="text-left p-4">Title</th>
                <th className="text-left p-4">Category</th>
                <th className="text-left p-4">Description</th>
                <th className="text-right p-4">Amount</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-text-secondary">
                    <TrendingUp className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No income entries yet</p>
                  </td>
                </tr>
              ) : (
                entries.map((entry) => (
                  <tr key={entry.id} className="table-row">
                    <td className="p-4 text-text-primary">{entry.entry_date}</td>
                    <td className="p-4 font-medium text-text-primary">{entry.title}</td>
                    <td className="p-4">
                      <span className="badge-info">
                        {INCOME_CATEGORIES.find(c => c.value === entry.category)?.label || entry.category}
                      </span>
                    </td>
                    <td className="p-4 text-text-secondary text-sm max-w-[200px] truncate">
                      {entry.description || '-'}
                    </td>
                    <td className="p-4 text-right font-semibold text-success">
                      ₹{entry.amount.toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
            {entries.length > 0 && (
              <tfoot className="bg-success/10">
                <tr>
                  <td colSpan={4} className="p-4 font-bold text-text-primary">Grand Total</td>
                  <td className="p-4 text-right font-bold text-success text-lg">
                    ₹{totalIncome.toLocaleString()}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>

      {/* Add Income Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Add Income Entry</DialogTitle>
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
                data-testid="income-title-input"
                className="input-field w-full"
                placeholder="e.g., March Maintenance Collection"
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
                  data-testid="income-category-select"
                  className="input-field w-full"
                >
                  {INCOME_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Date
                </label>
                <input
                  type="date"
                  value={formData.entry_date}
                  onChange={(e) => setFormData({ ...formData, entry_date: e.target.value })}
                  data-testid="income-date-input"
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
                data-testid="income-amount-input"
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
                data-testid="income-description-input"
                className="input-field w-full min-h-[80px]"
                placeholder="Additional notes..."
              />
            </div>
            
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
                data-testid="submit-income-btn"
                className="btn-primary disabled:opacity-50"
              >
                {saving ? 'Adding...' : 'Add Entry'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default IncomePage;
