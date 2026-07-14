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
import { ReasonDialog } from '../../components/ConfirmDialogs';

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
  const [excludeFlatId, setExcludeFlatId] = useState(null);
  const [cancelBillId, setCancelBillId] = useState(null);

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
      setExcludeFlatId(flatId);
    }
  };

  const confirmExcludeFlat = (reason) => {
    setExcludedFlats([...excludedFlats, excludeFlatId]);
    setCancelReasons({ ...cancelReasons, [excludeFlatId]: reason });
    setExcludeFlatId(null);
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

  const handleCancelBill = async (reason) => {
    try {
      await maintenanceAPI.cancelBill(cancelBillId, reason);
      toast.success('Bill cancelled');
      fetchBills(viewBillsMonth);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to cancel bill');
    } finally {
      setCancelBillId(null);
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

  const monthLabel = (m) => {
    if (!m) return '';
    const [y, mm] = m.split('-');
    const d = new Date(parseInt(y), parseInt(mm) - 1);
    return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-elevated rounded w-48" />
        <div className="h-96 bg-bg-elevated rounded-xl" />
      </div>
    );
  }

  // Aggregate summary for the selected batch
  const activeBills = bills.filter((b) => !b.is_cancelled);
  const verifiedCount = activeBills.filter((b) => b.status === 'verified').length;
  const paidCount = activeBills.filter((b) => b.status === 'paid').length;
  const pendingCount = activeBills.filter((b) => b.status === 'pending' || b.status === 'overdue').length;
  const totalAmount = activeBills.reduce((s, b) => s + b.amount, 0);
  const collectedAmount = activeBills.filter((b) => b.status === 'verified').reduce((s, b) => s + b.amount, 0);

  return (
    <div data-testid="maintenance-bills-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1>Maintenance Bills</h1>
          <p className="text-[12px]" style={{ color: '#5F5E5A' }}>Generate and manage monthly bills</p>
        </div>
        <button
          onClick={() => {
            setGenerateForm({ ...generateForm, month: getCurrentMonth() });
            setShowGenerateModal(true);
          }}
          data-testid="generate-bills-btn"
          className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center"
        >
          <Plus className="w-4 h-4" /> Generate Bills
        </button>
      </div>

      {/* Batch chips */}
      {batches.length > 0 && (
        <div className="tabs-scroll" data-testid="batch-chips">
          {batches.slice(0, 12).map((batch) => {
            const active = viewBillsMonth === batch.month;
            return (
              <button
                key={batch.id}
                onClick={() => setViewBillsMonth(batch.month)}
                data-testid={`batch-${batch.month}`}
                className="px-3 py-1.5 rounded-full text-[12px] font-medium transition-all whitespace-nowrap"
                style={
                  active
                    ? { backgroundColor: 'var(--accent-raw)', color: '#FFFFFF' }
                    : { backgroundColor: '#FFFFFF', color: '#1A1A18', border: '0.5px solid rgba(0,0,0,0.10)' }
                }
              >
                {monthLabel(batch.month)}
              </button>
            );
          })}
        </div>
      )}

      {/* Summary cards for selected batch */}
      {viewBillsMonth && bills.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="bills-summary">
          <div className="stat-card">
            <p className="stat-label">Total bills</p>
            <p className="stat-value">{bills.length}</p>
            <p className="stat-sub" style={{ color: '#5F5E5A' }}>₹{totalAmount.toLocaleString()}</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Verified</p>
            <p className="stat-value" style={{ color: '#3B6D11' }}>{verifiedCount}</p>
            <p className="stat-sub" style={{ color: '#3B6D11' }}>₹{collectedAmount.toLocaleString()} collected</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Awaiting</p>
            <p className="stat-value" style={{ color: '#0C447C' }}>{paidCount}</p>
            <p className="stat-sub" style={{ color: '#5F5E5A' }}>verification pending</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">Pending</p>
            <p className="stat-value text-outstanding">{pendingCount}</p>
            <p className="stat-sub text-outstanding">unpaid</p>
          </div>
        </div>
      )}

      {/* Bills Table */}
      {viewBillsMonth && (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: '0.5px solid rgba(0,0,0,0.06)' }}>
            <h2>Bills · {monthLabel(viewBillsMonth)}</h2>
            <span className="badge-neutral">{bills.length}</span>
          </div>
          <div className="table-mobile-wrapper">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="text-left p-3 sm:p-4">Flat</th>
                  <th className="text-left p-3 sm:p-4">Resident</th>
                  <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Wing</th>
                  <th className="text-left p-3 sm:p-4">Amount</th>
                  <th className="text-left p-3 sm:p-4">Status</th>
                  <th className="text-left p-3 sm:p-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {bills.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center" style={{ color: '#5F5E5A' }}>
                      <Receipt className="w-10 h-10 mx-auto mb-2 opacity-40" />
                      <p className="text-[12px]">No bills found for this month</p>
                    </td>
                  </tr>
                ) : (
                  bills.map((bill) => (
                    <tr key={bill.id} className="table-row" data-testid={`bill-${bill.id}`}>
                      <td className="p-3 sm:p-4 font-medium" style={{ color: '#1A1A18' }}>{bill.flat_number}</td>
                      <td className="p-3 sm:p-4 text-[12px]" style={{ color: '#1A1A18' }}>{bill.resident_name || '-'}</td>
                      <td className="p-3 sm:p-4 hidden sm:table-cell text-[12px]" style={{ color: '#5F5E5A' }}>{bill.wing_name}</td>
                      <td className="p-3 sm:p-4 font-medium" style={{ color: '#1A1A18' }}>₹{bill.amount}</td>
                      <td className="p-3 sm:p-4">{getStatusBadge(bill)}</td>
                      <td className="p-3 sm:p-4">
                        {!bill.is_cancelled && bill.status !== 'verified' && (
                          <button
                            onClick={() => setCancelBillId(bill.id)}
                            data-testid={`cancel-bill-${bill.id}`}
                            className="text-[11px] hover:underline"
                            style={{ color: '#A32D2D' }}
                          >
                            Cancel
                          </button>
                        )}
                        {bill.is_cancelled && (
                          <button
                            onClick={() => handleRestoreBill(bill.id)}
                            data-testid={`restore-bill-${bill.id}`}
                            className="text-[11px] hover:underline"
                            style={{ color: '#0C447C' }}
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
        <DialogContent className="card max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Generate Maintenance Bills</DialogTitle></DialogHeader>

          {!preview ? (
            <div className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Month</label>
                <input
                  type="month"
                  value={generateForm.month}
                  onChange={(e) => setGenerateForm({ ...generateForm, month: e.target.value })}
                  data-testid="month-input"
                  className="input-field"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Amount per Flat (₹)</label>
                <input
                  type="number"
                  value={generateForm.amountPerFlat}
                  onChange={(e) => setGenerateForm({ ...generateForm, amountPerFlat: parseInt(e.target.value) })}
                  data-testid="amount-input"
                  className="input-field"
                  min="1"
                  required
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowGenerateModal(false)} className="btn-secondary">Cancel</button>
                <button onClick={handlePreview} data-testid="preview-btn" className="btn-primary">Preview</button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className="stat-card">
                  <p className="stat-label">Total flats</p>
                  <p className="stat-value">{preview.total_active_flats}</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Per flat</p>
                  <p className="stat-value">₹{preview.amount_per_flat}</p>
                </div>
                <div className="stat-card">
                  <p className="stat-label">Total</p>
                  <p className="stat-value" style={{ color: 'var(--accent-raw)' }}>
                    ₹{((preview.total_active_flats - excludedFlats.length) * preview.amount_per_flat).toLocaleString()}
                  </p>
                </div>
              </div>

              <div className="text-[12px] flex items-center gap-2" style={{ color: '#5F5E5A' }}>
                <AlertTriangle className="w-4 h-4" style={{ color: '#854F0B' }} />
                Click on a flat to exclude it from billing
              </div>

              <div className="max-h-[400px] overflow-y-auto rounded-lg" style={{ border: '0.5px solid rgba(0,0,0,0.10)' }}>
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
                          className="cursor-pointer transition-colors table-row"
                          style={isExcluded ? { backgroundColor: '#FCEBEB' } : undefined}
                        >
                          <td className="p-3" style={{ color: isExcluded ? '#A32D2D' : '#1A1A18' }}>{flat.number}</td>
                          <td className="p-3" style={{ color: isExcluded ? '#A32D2D' : '#1A1A18' }}>{flat.wing_name}</td>
                          <td className="p-3" style={{ color: isExcluded ? '#A32D2D' : '#1A1A18' }}>{flat.resident_name || '-'}</td>
                          <td className="p-3" style={{ color: isExcluded ? '#A32D2D' : '#1A1A18', textDecoration: isExcluded ? 'line-through' : 'none' }}>
                            ₹{flat.amount}
                          </td>
                          <td className="p-3">
                            {isExcluded ? <span className="badge-danger">Excluded</span> : <span className="badge-success">Include</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex gap-2 justify-end">
                <button onClick={() => setPreview(null)} className="btn-secondary">Back</button>
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

      <ReasonDialog
        open={!!excludeFlatId}
        onOpenChange={(open) => !open && setExcludeFlatId(null)}
        title="Exclude Flat"
        description="Enter the reason for excluding this flat from bill generation."
        placeholder="e.g. Flat vacant this month"
        submitLabel="Exclude Flat"
        onSubmit={confirmExcludeFlat}
        testIdPrefix="exclude-flat"
      />

      <ReasonDialog
        open={!!cancelBillId}
        onOpenChange={(open) => !open && setCancelBillId(null)}
        title="Cancel Bill"
        description="Enter the reason for cancelling this bill."
        placeholder="e.g. Duplicate bill generated"
        submitLabel="Cancel Bill"
        onSubmit={handleCancelBill}
        testIdPrefix="cancel-bill"
      />
    </div>
  );
};

export default MaintenanceBills;
