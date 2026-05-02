import { useState, useEffect } from 'react';
import { Bell, MessageSquare, Plus, Pin, Trash2, AlertTriangle, ShoppingBag, ExternalLink } from 'lucide-react';
import { miscAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

const NoticesPage = () => {
  const { user } = useAuthStore();
  const [notices, setNotices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ title: '', content: '', is_pinned: false });
  const [saving, setSaving] = useState(false);

  const isAdmin = user?.role === 'admin';

  const fetchNotices = async () => {
    try {
      const res = await miscAPI.getNotices();
      setNotices(res.data);
    } catch (e) {
      toast.error('Failed to load notices');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotices();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await miscAPI.createNotice(formData);
      toast.success('Notice created');
      setShowModal(false);
      setFormData({ title: '', content: '', is_pinned: false });
      fetchNotices();
    } catch (e) {
      toast.error('Failed to create notice');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (noticeId) => {
    if (!window.confirm('Delete this notice?')) return;
    try {
      await miscAPI.deleteNotice(noticeId);
      toast.success('Notice deleted');
      fetchNotices();
    } catch (e) {
      toast.error('Failed to delete notice');
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 bg-bg-surface rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="notices-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Notice Board</h1>
          <p className="text-text-secondary mt-1">Important announcements</p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowModal(true)}
            data-testid="create-notice-btn"
            className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center"
          >
            <Plus className="w-5 h-5" />
            New Notice
          </button>
        )}
      </div>

      {notices.length === 0 ? (
        <div className="card p-12 text-center">
          <Bell className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Notices</h3>
          <p className="text-text-secondary">No announcements at this time</p>
        </div>
      ) : (
        <div className="space-y-4">
          {notices.map((notice) => (
            <div
              key={notice.id}
              className={`card p-6 ${notice.is_pinned ? 'border-l-4 border-l-accent' : ''}`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {notice.is_pinned && (
                    <Pin className="w-4 h-4 text-accent" />
                  )}
                  <h3 className="text-lg font-semibold text-text-primary">{notice.title}</h3>
                </div>
                {isAdmin && (
                  <button
                    onClick={() => handleDelete(notice.id)}
                    data-testid={`delete-notice-${notice.id}`}
                    className="p-2 text-text-muted hover:text-danger hover:bg-danger/10 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                )}
              </div>
              <p className="text-text-secondary whitespace-pre-wrap">{notice.content}</p>
              <div className="mt-4 flex items-center gap-4 text-sm text-text-muted">
                <span>By {notice.created_by_name}</span>
                <span>•</span>
                <span>{new Date(notice.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Create Notice</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="notice-title-input"
                className="input-field w-full"
                placeholder="Notice title"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Content
              </label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                data-testid="notice-content-input"
                className="input-field w-full min-h-[150px]"
                placeholder="Notice content..."
                required
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_pinned}
                onChange={(e) => setFormData({ ...formData, is_pinned: e.target.checked })}
                className="rounded"
              />
              <span className="text-text-secondary">Pin this notice</span>
            </label>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={saving} data-testid="create-notice-submit" className="btn-primary disabled:opacity-50">
                {saving ? 'Creating...' : 'Create Notice'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const ComplaintsPage = () => {
  const { user } = useAuthStore();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    category: 'general',
    priority: 'medium',
    description: '',
  });
  const [saving, setSaving] = useState(false);

  const isResident = user?.role === 'resident' || user?.role === 'sub_admin';
  const canManage = user?.role === 'admin' || user?.role === 'sub_admin';

  const fetchComplaints = async () => {
    try {
      const res = await miscAPI.getComplaints();
      setComplaints(res.data);
    } catch (e) {
      toast.error('Failed to load complaints');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await miscAPI.createComplaint(formData);
      toast.success('Complaint submitted');
      setShowModal(false);
      setFormData({ title: '', category: 'general', priority: 'medium', description: '' });
      fetchComplaints();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to submit complaint');
    } finally {
      setSaving(false);
    }
  };

  const handleStatusUpdate = async (complaintId, status) => {
    try {
      await miscAPI.updateComplaintStatus(complaintId, { status });
      toast.success('Status updated');
      fetchComplaints();
    } catch (e) {
      toast.error('Failed to update status');
    }
  };

  const getPriorityBadge = (priority) => {
    switch (priority) {
      case 'urgent':
        return <span className="badge-danger">Urgent</span>;
      case 'high':
        return <span className="badge-warning">High</span>;
      case 'medium':
        return <span className="badge-info">Medium</span>;
      case 'low':
        return <span className="badge-success">Low</span>;
      default:
        return <span className="badge-info">{priority}</span>;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'resolved':
      case 'closed':
        return <span className="badge-success">{status}</span>;
      case 'in_progress':
        return <span className="badge-warning">In Progress</span>;
      case 'open':
        return <span className="badge-danger">Open</span>;
      default:
        return <span className="badge-info">{status}</span>;
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
    <div data-testid="complaints-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Complaints</h1>
          <p className="text-text-secondary mt-1">Report and track issues</p>
        </div>
        {isResident && (
          <button
            onClick={() => setShowModal(true)}
            data-testid="create-complaint-btn"
            className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center"
          >
            <Plus className="w-5 h-5" />
            New Complaint
          </button>
        )}
      </div>

      {complaints.length === 0 ? (
        <div className="card p-12 text-center">
          <MessageSquare className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Complaints</h3>
          <p className="text-text-secondary">No complaints filed yet</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="table-mobile-wrapper">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="text-left p-3 sm:p-4">Title</th>
                  <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Category</th>
                  <th className="text-left p-3 sm:p-4">Priority</th>
                  <th className="text-left p-3 sm:p-4">Status</th>
                  <th className="text-left p-3 sm:p-4 hidden md:table-cell">Date</th>
                  {canManage && <th className="text-left p-3 sm:p-4">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {complaints.map((complaint) => (
                  <tr key={complaint.id} className="table-row">
                    <td className="p-3 sm:p-4">
                      <div>
                        <p className="font-medium text-text-primary text-sm">{complaint.title}</p>
                        <p className="text-xs text-text-secondary truncate max-w-[120px] sm:max-w-[200px]">
                          {complaint.description}
                        </p>
                      </div>
                    </td>
                    <td className="p-3 sm:p-4 hidden sm:table-cell">
                      <span className="badge-info">{complaint.category}</span>
                    </td>
                    <td className="p-3 sm:p-4">{getPriorityBadge(complaint.priority)}</td>
                    <td className="p-3 sm:p-4">{getStatusBadge(complaint.status)}</td>
                    <td className="p-3 sm:p-4 text-text-secondary text-sm hidden md:table-cell">
                      {new Date(complaint.created_at).toLocaleDateString()}
                    </td>
                    {canManage && (
                      <td className="p-3 sm:p-4">
                        <select
                          value={complaint.status}
                          onChange={(e) => handleStatusUpdate(complaint.id, e.target.value)}
                          data-testid={`update-status-${complaint.id}`}
                          className="input-field text-xs sm:text-sm py-1"
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In Progress</option>
                          <option value="resolved">Resolved</option>
                          <option value="closed">Closed</option>
                        </select>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="bg-bg-surface border-border-color">
          <DialogHeader>
            <DialogTitle className="text-text-primary">Submit Complaint</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="complaint-title-input"
                className="input-field w-full"
                placeholder="Brief description of the issue"
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
                  data-testid="complaint-category-select"
                  className="input-field w-full"
                >
                  <option value="plumbing">Plumbing</option>
                  <option value="electrical">Electrical</option>
                  <option value="sanitation">Sanitation</option>
                  <option value="parking">Parking</option>
                  <option value="security">Security</option>
                  <option value="general">General</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Priority
                </label>
                <select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  data-testid="complaint-priority-select"
                  className="input-field w-full"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                data-testid="complaint-description-input"
                className="input-field w-full min-h-[100px]"
                placeholder="Detailed description..."
                required
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={saving} data-testid="submit-complaint-btn" className="btn-primary disabled:opacity-50">
                {saving ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const BazaarPage = () => {
  const [link, setLink] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLink = async () => {
      try {
        const res = await miscAPI.getBazaarLink();
        setLink(res.data);
      } catch (e) {
        console.error('Failed to load bazaar link');
      } finally {
        setLoading(false);
      }
    };
    fetchLink();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-64 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="bazaar-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Bazaar</h1>
        <p className="text-text-secondary mt-1">Redeem your wallet points</p>
      </div>

      <div className="card p-8 max-w-md mx-auto text-center">
        <div className="p-6 bg-accent/20 rounded-full w-24 h-24 mx-auto mb-6 flex items-center justify-center">
          <ShoppingBag className="w-12 h-12 text-accent" />
        </div>
        
        {link?.available ? (
          <>
            <h3 className="text-xl font-semibold text-text-primary mb-4">
              Shop with your Points!
            </h3>
            <p className="text-text-secondary mb-6">
              Use your wallet points to shop at our partner store.
            </p>
            <a
              href={link.shopping_link}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="bazaar-link"
              className="btn-primary inline-flex items-center gap-2"
            >
              Go to Bazaar
              <ExternalLink className="w-4 h-4" />
            </a>
          </>
        ) : (
          <>
            <h3 className="text-xl font-semibold text-text-primary mb-4">
              Coming Soon!
            </h3>
            <p className="text-text-secondary">
              The bazaar feature is being set up. Check back later to redeem your points.
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export { NoticesPage, ComplaintsPage, BazaarPage };
