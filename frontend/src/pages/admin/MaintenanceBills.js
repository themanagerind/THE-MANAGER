import { useState, useEffect } from 'react';
import { Receipt, Plus, Calendar, IndianRupee, Eye, X, AlertTriangle } from 'lucide-react';
import { maintenanceAPI, adminAPI } from '../../lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const MaintenanceBills = () => {
  const [batches, setBatches] = useState([]);
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState('');
  const [preview, setPreview] = useState(null);
  const [generateForm, setGenerateForm] = useState({
    month: '',
    amountPerFlat: 1200,
  });
  const [excludedFlats, setExcludedFlats] = useState([]);
  const [cancelReasons, setCancelReasons] = useState({});
  const [generating, setGenerating] = useState(false);
  const [viewBillsMonth, setViewBillsMonth] = useState('');

  const fetchData = async () => {
    try {
      const batchesRes = await maintenanceAPI.getBatches();
      setBatches(batchesRes.data);
      
      if (batchesRes.data.length > 0 && !viewBillsMonth) {
        setViewBillsMonth(batchesRes.data[0].month);
      }
    } catch (e) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchBills = async (month) => {
    if (!month) return;
    try {
      const billsRes = await maintenanceAPI.getBills({ month });
      setBills(billsRes.data);
    } catch (e) {
      toast.error('Failed to load bills');
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (viewBillsMonth) {
      fetchBills(viewBillsMonth);
    }
  }, [viewBillsMonth]);

  const handlePreview = async () => {
    if (!generateForm.month || !generateForm.amountPerFlat) {
      toast.error('Please fill all fields');
      return;
    }
    
    try {
      const res = await maintenanceAPI.preview(generateForm.month, generateForm.amountPerFlat);
      setPreview(res.data);
      setExcludedFlats([]);
      setCancelReasons({});
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate preview');
    }
  };

  const handleExcludeFlat = (flatId) => {
    if (excludedFlats.includes(flatId)) {
      setExcludedFlats(excludedFlats.filter(id => id !== flatId));
      const newReasons = { ...cancelReasons };
      delete newReasons[flatId];
      setCancelReasons(newReasons);
    } else {
      const reason = prompt('Enter reason for excluding this flat:');
      if (reason) {
        setExcludedFlats([...excludedFlats, flatId]);
        setCancelReasons({ ...cancelReasons, [flatId]: reason });
      }
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await maintenanceAPI.generate({
        month: generateForm.month,
        amount_per_flat: generateForm.amountPerFlat,
        excluded_flat_ids: excludedFlats,
        cancel_reasons: cancelReasons,
      });
      toast.success('Bills generated successfully');
      setShowGenerateModal(false);
      setPreview(null);
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate bills');
    } finally {
      setGenerating(false);
    }
  };

  const handleCancelBill = async (billId) => {
    const reason = prompt('Enter reason for cancellation:');
    if (!reason) return;
    
    try {
      await maintenanceAPI.cancelBill(billId, reason);
      toast.success('Bill cancelled');
      fetchBills(viewBillsMonth);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to cancel bill');
    }
  };

  const handleRestoreBill = async (billId) => {
    try {
      await maintenanceAPI.restoreBill(billId);
      toast.success('Bill restored');
      fetchBills(viewBillsMonth);
    } catch (e) {
      toast.error('Failed to restore bill');
    }
  };

  const getStatusBadge = (bill) => {
    if (bill.is_cancelled) {
      return <span className="badge-danger">Cancelled</span>;
    }
    switch (bill.status) {
      case 'verified':
        return <span className="badge-success">Verified</span>;
      case 'paid':
        return <span className="badge-info">Paid</span>;
      case 'pending':
        return <span className="badge-warning">Pending</span>;
      case 'overdue':
        return <span className="badge-danger">Overdue</span>;
      default:
        return <span className="badge-info">{bill.status}</span>;
    }
  };

  const getCurrentMonth = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
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
    <div data-testid="maintenance-bills-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Maintenance Bills</h1>
          <p className="text-text-secondary mt-1">Generate and manage monthly bills</p>
        </div>
        <button
          onClick={() => {
            setGenerateForm({ ...generateForm, month: getCurrentMonth() });
            setShowGenerateModal(true);
          }}
          data-testid="generate-bills-btn"
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Generate Bills
        </button>
      </div>

      {/* Batches Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {batches.slice(0, 4).map((batch) => (
          <button
            key={batch.id}
            onClick={() => setViewBillsMonth(batch.month)}
            data-testid={`batch-${batch.month}`}
            className={`card p-4 text-left transition-all ${
              viewBillsMonth === batch.month ? 'ring-2 ring-accent' : ''
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-text-secondary text-sm">{batch.month}</span>
              <Calendar className="w-4 h-4 text-text-muted" />
            </div>
            <p className="text-xl font-bold text-text-primary">
              ₹{batch.total_amount.toLocaleString()}
            </p>
            <p className="text-sm text-text-secondary">
              {batch.billed_flats} flats @ ₹{batch.amount_per_flat}
            </p>
          </button>
        ))}
      </div>

      {/* Bills Table */}
      {viewBillsMonth && (
        <div className="card overflow-hidden">
          <div className="p-4 border-b border-border-color">
            <h3 className="font-semibold text-text-primary">Bills for {viewBillsMonth}</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="text-left p-4">Flat</th>
                  <th className="text-left p-4">Resident</th>
                  <th className="text-left p-4">Wing</th>
                  <th className="text-left p-4">Amount</th>
                  <th className="text-left p-4">Status</th>
                  <th className="text-left p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {bills.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-text-secondary">
                      <Receipt className="w-12 h-12 mx-auto mb-2 opacity-50" />
                      <p>No bills found</p>
                    </td>
                  </tr>
                ) : (
                  bills.map((bill) => (
                    <tr key={bill.id} className="table-row">
                      <td className="p-4 font-medium text-text-primary">{bill.flat_number}</td>
                      <td className="p-4 text-text-primary">{bill.resident_name || '-'}</td>
                      <td className="p-4 text-text-primary">{bill.wing_name}</td>
                      <td className="p-4 text-text-primary">₹{bill.amount}</td>
                      <td className="p-4">{getStatusBadge(bill)}</td>
                      <td className="p-4">
                        {!bill.is_cancelled && bill.status !== 'verified' && (
                          <button
                            onClick={() => handleCancelBill(bill.id)}
                            data-testid={`cancel-bill-${bill.id}`}
                            className="text-sm text-danger hover:underline"
                          >
                            Cancel
                          </button>
                        )}
                        {bill.is_cancelled && (
                          <button
                            onClick={() => handleRestoreBill(bill.id)}
                            data-testid={`restore-bill-${bill.id}`}
                            className="text-sm text-info hover:underline"
                          >
                            Restore
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Generate Modal */}
      <Dialog open={showGenerateModal} onOpenChange={setShowGenerateModal}>
        <DialogContent className="bg-bg-surface border-border-color max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Generate Maintenance Bills</DialogTitle>
          </DialogHeader>
          
          {!preview ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Month
                </label>
                <input
                  type="month"
                  value={generateForm.month}
                  onChange={(e) => setGenerateForm({ ...generateForm, month: e.target.value })}
                  data-testid="month-input"
                  className="input-field w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Amount per Flat (₹)
                </label>
                <input
                  type="number"
                  value={generateForm.amountPerFlat}
                  onChange={(e) => setGenerateForm({ ...generateForm, amountPerFlat: parseInt(e.target.value) })}
                  data-testid="amount-input"
                  className="input-field w-full"
                  min="1"
                  required
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowGenerateModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={handlePreview}
                  data-testid="preview-btn"
                  className="btn-primary"
                >
                  Preview
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="card p-4 bg-bg-elevated">
                  <p className="text-text-secondary text-sm">Total Flats</p>
                  <p className="text-2xl font-bold text-text-primary">{preview.total_active_flats}</p>
                </div>
                <div className="card p-4 bg-bg-elevated">
                  <p className="text-text-secondary text-sm">Amount/Flat</p>
                  <p className="text-2xl font-bold text-text-primary">₹{preview.amount_per_flat}</p>
                </div>
                <div className="card p-4 bg-bg-elevated">
                  <p className="text-text-secondary text-sm">Total Amount</p>
                  <p className="text-2xl font-bold text-accent">
                    ₹{((preview.total_active_flats - excludedFlats.length) * preview.amount_per_flat).toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="text-sm text-text-secondary flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-warning" />
                Click on a flat to exclude it from billing
              </div>

              <div className="max-h-[400px] overflow-y-auto border border-border-color rounded-lg">
                <table className="w-full">
                  <thead className="table-header sticky top-0">
                    <tr>
                      <th className="text-left p-3">Flat</th>
                      <th className="text-left p-3">Wing</th>
                      <th className="text-left p-3">Resident</th>
                      <th className="text-left p-3">Amount</th>
                      <th className="text-left p-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.flats.map((flat) => {
                      const isExcluded = excludedFlats.includes(flat.id);
                      return (
                        <tr
                          key={flat.id}
                          onClick={() => handleExcludeFlat(flat.id)}
                          data-testid={`preview-flat-${flat.id}`}
                          className={`cursor-pointer transition-colors ${
                            isExcluded
                              ? 'bg-danger/10 hover:bg-danger/20'
                              : 'hover:bg-bg-elevated'
                          }`}
                        >
                          <td className={`p-3 ${isExcluded ? 'text-danger' : 'text-text-primary'}`}>
                            {flat.number}
                          </td>
                          <td className={`p-3 ${isExcluded ? 'text-danger' : 'text-text-primary'}`}>
                            {flat.wing_name}
                          </td>
                          <td className={`p-3 ${isExcluded ? 'text-danger' : 'text-text-primary'}`}>
                            {flat.resident_name || '-'}
                          </td>
                          <td className={`p-3 ${isExcluded ? 'text-danger line-through' : 'text-text-primary'}`}>
                            ₹{flat.amount}
                          </td>
                          <td className="p-3">
                            {isExcluded ? (
                              <span className="badge-danger">Excluded</span>
                            ) : (
                              <span className="badge-success">Include</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setPreview(null)}
                  className="btn-secondary"
                >
                  Back
                </button>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  data-testid="generate-submit-btn"
                  className="btn-primary disabled:opacity-50"
                >
                  {generating ? 'Generating...' : `Generate ${preview.total_active_flats - excludedFlats.length} Bills`}
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MaintenanceBills;
