import { useState, useEffect } from 'react';
import { ClipboardList, Plus, CheckCircle, XCircle, Clock, Users, AlertCircle } from 'lucide-react';
import { adminAPI } from '../../lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const PlansPage = () => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    amount: '',
  });

  const fetchPlans = async () => {
    try {
      const res = await adminAPI.getPlans();
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await adminAPI.createPlan({
        title: formData.title,
        description: formData.description,
        amount: formData.amount ? parseFloat(formData.amount) : null,
      });
      toast.success('Plan created and sent for approval');
      setShowModal(false);
      setFormData({ title: '', description: '', amount: '' });
      fetchPlans();
    } catch (e) {
      toast.error('Failed to create plan');
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'approved':
        return <span className="badge-success flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Approved</span>;
      case 'rejected':
        return <span className="badge-danger flex items-center gap-1"><XCircle className="w-3 h-3" /> Rejected</span>;
      case 'pending_approval':
        return <span className="badge-warning flex items-center gap-1"><Clock className="w-3 h-3" /> Pending Approval</span>;
      default:
        return <span className="badge-info">{status}</span>;
    }
  };

  const getApprovalProgress = (approvals) => {
    if (!approvals || approvals.length === 0) return { approved: 0, total: 0, pending: 0 };
    const approved = approvals.filter(a => a.decision === 'approved').length;
    const pending = approvals.filter(a => a.decision === 'pending').length;
    return { approved, total: approvals.length, pending };
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
    <div data-testid="plans-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Plans</h1>
          <p className="text-text-secondary mt-1">Create and manage society plans</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          data-testid="add-plan-btn"
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Create Plan
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4">
          <p className="text-text-secondary text-sm">Total Plans</p>
          <p className="text-2xl font-bold text-text-primary">{plans.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-text-secondary text-sm">Approved</p>
          <p className="text-2xl font-bold text-success">
            {plans.filter(p => p.status === 'approved').length}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-text-secondary text-sm">Pending</p>
          <p className="text-2xl font-bold text-warning">
            {plans.filter(p => p.status === 'pending_approval').length}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-text-secondary text-sm">Rejected</p>
          <p className="text-2xl font-bold text-danger">
            {plans.filter(p => p.status === 'rejected').length}
          </p>
        </div>
      </div>

      {/* Plans List */}
      {plans.length === 0 ? (
        <div className="card p-12 text-center">
          <ClipboardList className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Plans Yet</h3>
          <p className="text-text-secondary mb-4">Create your first plan to get sub-admin approvals</p>
          <button onClick={() => setShowModal(true)} className="btn-primary">
            Create Plan
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {plans.map((plan) => {
            const progress = getApprovalProgress(plan.approvals);
            
            return (
              <div key={plan.id} className="card p-6">
                <div className="flex items-start justify-between mb-4">
                  {getStatusBadge(plan.status)}
                  {plan.amount && (
                    <span className="text-accent font-semibold">
                      ₹{plan.amount.toLocaleString()}
                    </span>
                  )}
                </div>
                
                <h3 className="text-xl font-semibold text-text-primary mb-2">{plan.title}</h3>
                <p className="text-text-secondary mb-4 line-clamp-2">{plan.description}</p>
                
                {/* Approval Progress */}
                {plan.approvals && plan.approvals.length > 0 && (
                  <div className="mb-4">
                    <div className="flex items-center justify-between text-sm text-text-secondary mb-2">
                      <span className="flex items-center gap-1">
                        <Users className="w-4 h-4" />
                        Approval Progress
                      </span>
                      <span>{progress.approved}/{progress.total}</span>
                    </div>
                    <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                      <div
                        className="h-full bg-success transition-all"
                        style={{ width: `${(progress.approved / progress.total) * 100}%` }}
                      />
                    </div>
                  </div>
                )}
                
                {/* Rejection Reasons */}
                {plan.status === 'rejected' && plan.rejection_reasons?.length > 0 && (
                  <div className="mt-4 p-3 bg-danger/10 rounded-lg border border-danger/30">
                    <p className="text-danger text-sm font-medium flex items-center gap-1 mb-2">
                      <AlertCircle className="w-4 h-4" />
                      Rejection Reasons:
                    </p>
                    {plan.rejection_reasons.map((r, i) => (
                      <p key={i} className="text-danger/80 text-sm">
                        • <strong>{r.sub_admin_name}:</strong> {r.reason}
                      </p>
                    ))}
                  </div>
                )}
                
                {/* Approvals Detail */}
                <button
                  onClick={() => setSelectedPlan(selectedPlan?.id === plan.id ? null : plan)}
                  className="text-sm text-accent hover:underline mt-2"
                  data-testid={`view-approvals-${plan.id}`}
                >
                  {selectedPlan?.id === plan.id ? 'Hide Details' : 'View Approval Details'}
                </button>
                
                {selectedPlan?.id === plan.id && plan.approvals && (
                  <div className="mt-4 space-y-2 p-3 bg-bg-elevated rounded-lg">
                    {plan.approvals.map((approval, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-text-primary">{approval.sub_admin_name}</span>
                        <span className={`font-medium ${
                          approval.decision === 'approved' ? 'text-success' :
                          approval.decision === 'rejected' ? 'text-danger' :
                          'text-warning'
                        }`}>
                          {approval.decision.charAt(0).toUpperCase() + approval.decision.slice(1)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                
                <p className="text-text-muted text-xs mt-4">
                  Created: {new Date(plan.created_at).toLocaleDateString()}
                </p>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Plan Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Create New Plan</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Plan Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="plan-title-input"
                className="input-field w-full"
                placeholder="e.g., New Security System"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                data-testid="plan-description-input"
                className="input-field w-full min-h-[120px]"
                placeholder="Describe the plan in detail..."
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Estimated Amount (Optional)
              </label>
              <input
                type="number"
                value={formData.amount}
                onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                data-testid="plan-amount-input"
                className="input-field w-full"
                placeholder="₹0"
                min="0"
              />
            </div>
            
            <p className="text-text-secondary text-sm bg-bg-elevated p-3 rounded-lg">
              <strong>Note:</strong> This plan will require approval from ALL sub-admins before it can proceed.
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
                data-testid="submit-plan-btn"
                className="btn-primary disabled:opacity-50"
              >
                {saving ? 'Creating...' : 'Create Plan'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PlansPage;
