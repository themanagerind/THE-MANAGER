import { useState, useEffect, useMemo } from 'react';
import {
  Bell, MessageSquare, Plus, Pin, Trash2, AlertTriangle, ShoppingBag, ExternalLink,
  X, Filter, Calendar, User, Tag, Wallet, ArrowRight, CheckCircle2, Clock, Sparkles,
} from 'lucide-react';
import { miscAPI, maintenanceAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';

// ============== Time-ago helper ==============
const timeAgo = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return 'just now';
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  if (d < 30) return `${Math.floor(d / 7)}w ago`;
  return date.toLocaleDateString();
};

// ============== Notice Board ==============
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

  useEffect(() => { fetchNotices(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await miscAPI.createNotice(formData);
      toast.success('Notice posted');
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

  const pinned = notices.filter((n) => n.is_pinned);
  const others = notices.filter((n) => !n.is_pinned);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-elevated rounded w-48" />
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => <div key={i} className="h-28 bg-bg-elevated rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="notices-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1>Notice Board</h1>
          <p className="text-[12px]" style={{ color: '#5F5E5A' }}>
            {notices.length} {notices.length === 1 ? 'announcement' : 'announcements'}
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowModal(true)}
            data-testid="create-notice-btn"
            className="btn-primary hidden sm:flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> New Notice
          </button>
        )}
      </div>

      {notices.length === 0 ? (
        <div className="card p-10 text-center">
          <div className="w-14 h-14 mx-auto mb-3 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--accent-light)' }}>
            <Bell className="w-6 h-6" style={{ color: 'var(--accent-raw)' }} />
          </div>
          <h2>No notices yet</h2>
          <p className="text-[12px] mt-1" style={{ color: '#5F5E5A' }}>Important announcements will appear here</p>
          {isAdmin && (
            <button onClick={() => setShowModal(true)} className="btn-primary mt-4">
              <Plus className="w-4 h-4 inline mr-1" /> Post first notice
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-5">
          {pinned.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2 px-1">
                <Pin className="w-3.5 h-3.5" style={{ color: 'var(--accent-raw)' }} />
                <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: 'var(--accent-raw)' }}>
                  Pinned
                </span>
              </div>
              <div className="space-y-3">
                {pinned.map((n) => (
                  <NoticeCard key={n.id} notice={n} isAdmin={isAdmin} onDelete={handleDelete} accent />
                ))}
              </div>
            </div>
          )}

          {others.length > 0 && (
            <div>
              {pinned.length > 0 && (
                <div className="flex items-center gap-2 mb-2 px-1">
                  <span className="text-[10px] uppercase tracking-wider font-medium" style={{ color: '#5F5E5A' }}>
                    All notices
                  </span>
                </div>
              )}
              <div className="space-y-3">
                {others.map((n) => (
                  <NoticeCard key={n.id} notice={n} isAdmin={isAdmin} onDelete={handleDelete} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mobile FAB */}
      {isAdmin && (
        <button
          onClick={() => setShowModal(true)}
          data-testid="create-notice-fab"
          className="sm:hidden fixed right-4 z-30 rounded-full flex items-center justify-center"
          style={{
            bottom: 'calc(72px + env(safe-area-inset-bottom, 0px))',
            width: 52, height: 52,
            backgroundColor: 'var(--accent-raw)',
            color: '#FFFFFF',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}
          aria-label="New Notice"
        >
          <Plus className="w-6 h-6" />
        </button>
      )}

      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="card max-w-lg">
          <DialogHeader>
            <DialogTitle>Post a notice</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>
                Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="notice-title-input"
                className="input-field"
                placeholder="e.g., Water tank cleaning on Sunday"
                required
              />
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>
                Content
              </label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                data-testid="notice-content-input"
                className="input-field"
                style={{ minHeight: 140, padding: '10px 12px', height: 'auto' }}
                placeholder="Write the full notice content..."
                required
              />
            </div>
            <label className="flex items-center gap-2 cursor-pointer p-3 rounded-lg" style={{ backgroundColor: 'var(--accent-light)' }}>
              <input
                type="checkbox"
                checked={formData.is_pinned}
                onChange={(e) => setFormData({ ...formData, is_pinned: e.target.checked })}
                style={{ accentColor: 'var(--accent-raw)' }}
              />
              <Pin className="w-4 h-4" style={{ color: 'var(--accent-raw)' }} />
              <span className="text-[12px]" style={{ color: 'var(--accent-raw)' }}>Pin to top</span>
            </label>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} data-testid="create-notice-submit" className="btn-primary disabled:opacity-50">
                {saving ? 'Posting...' : 'Post Notice'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const NoticeCard = ({ notice, isAdmin, onDelete, accent = false }) => (
  <div
    className="card p-4 sm:p-5"
    style={accent ? { borderLeft: '3px solid var(--accent-raw)' } : undefined}
    data-testid={`notice-card-${notice.id}`}
  >
    <div className="flex items-start justify-between gap-3 mb-2">
      <h2 className="flex-1 leading-snug">{notice.title}</h2>
      {isAdmin && (
        <button
          onClick={() => onDelete(notice.id)}
          data-testid={`delete-notice-${notice.id}`}
          className="p-1.5 rounded hover:bg-black/5 -mt-1 -mr-1 transition-colors"
          aria-label="Delete notice"
        >
          <Trash2 className="w-4 h-4" style={{ color: '#A32D2D' }} />
        </button>
      )}
    </div>
    <p className="text-[13px] whitespace-pre-wrap" style={{ color: '#5F5E5A', lineHeight: 1.55 }}>
      {notice.content}
    </p>
    <div className="flex items-center gap-3 text-[11px] mt-3 pt-3 border-t" style={{ borderColor: 'rgba(0,0,0,0.06)', color: '#888780' }}>
      <span className="flex items-center gap-1"><User className="w-3 h-3" /> {notice.created_by_name}</span>
      <span>•</span>
      <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {timeAgo(notice.created_at)}</span>
    </div>
  </div>
);

// ============== Complaints with Detail View ==============
const ComplaintsPage = () => {
  const { user } = useAuthStore();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [detail, setDetail] = useState(null);
  const [filter, setFilter] = useState('all');
  const [formData, setFormData] = useState({
    title: '', category: 'general', priority: 'medium', description: '',
  });
  const [saving, setSaving] = useState(false);

  const isResident = user?.role === 'resident';
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

  useEffect(() => { fetchComplaints(); }, []);

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
      if (detail && detail.id === complaintId) {
        setDetail({ ...detail, status });
      }
    } catch (e) {
      toast.error('Failed to update status');
    }
  };

  const filtered = useMemo(() => {
    if (filter === 'all') return complaints;
    return complaints.filter((c) => c.status === filter);
  }, [filter, complaints]);

  const counts = useMemo(() => ({
    all: complaints.length,
    open: complaints.filter((c) => c.status === 'open').length,
    in_progress: complaints.filter((c) => c.status === 'in_progress').length,
    resolved: complaints.filter((c) => c.status === 'resolved' || c.status === 'closed').length,
  }), [complaints]);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-elevated rounded w-48" />
        <div className="h-96 bg-bg-elevated rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="complaints-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1>Complaints</h1>
          <p className="text-[12px]" style={{ color: '#5F5E5A' }}>Report and track issues</p>
        </div>
        {isResident && (
          <button
            onClick={() => setShowModal(true)}
            data-testid="create-complaint-btn"
            className="btn-primary hidden sm:flex items-center gap-2"
          >
            <Plus className="w-4 h-4" /> New Complaint
          </button>
        )}
      </div>

      {/* Filter chips */}
      <div className="tabs-scroll">
        <FilterChip active={filter === 'all'} onClick={() => setFilter('all')} count={counts.all} testid="filter-all">All</FilterChip>
        <FilterChip active={filter === 'open'} onClick={() => setFilter('open')} count={counts.open} testid="filter-open">Open</FilterChip>
        <FilterChip active={filter === 'in_progress'} onClick={() => setFilter('in_progress')} count={counts.in_progress} testid="filter-in-progress">In Progress</FilterChip>
        <FilterChip active={filter === 'resolved'} onClick={() => setFilter('resolved')} count={counts.resolved} testid="filter-resolved">Resolved</FilterChip>
      </div>

      {filtered.length === 0 ? (
        <div className="card p-10 text-center">
          <div className="w-14 h-14 mx-auto mb-3 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--accent-light)' }}>
            <MessageSquare className="w-6 h-6" style={{ color: 'var(--accent-raw)' }} />
          </div>
          <h2>{filter === 'all' ? 'No complaints filed yet' : 'No matching complaints'}</h2>
          <p className="text-[12px] mt-1" style={{ color: '#5F5E5A' }}>
            {filter === 'all' ? 'When residents file issues they will appear here' : 'Try a different filter'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((c) => (
            <ComplaintCard key={c.id} complaint={c} onClick={() => setDetail(c)} />
          ))}
        </div>
      )}

      {/* Mobile FAB */}
      {isResident && (
        <button
          onClick={() => setShowModal(true)}
          data-testid="create-complaint-fab"
          className="sm:hidden fixed right-4 z-30 rounded-full flex items-center justify-center"
          style={{
            bottom: 'calc(72px + env(safe-area-inset-bottom, 0px))',
            width: 52, height: 52,
            backgroundColor: 'var(--accent-raw)',
            color: '#FFFFFF',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}
          aria-label="New Complaint"
        >
          <Plus className="w-6 h-6" />
        </button>
      )}

      {/* Create modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="card max-w-lg">
          <DialogHeader><DialogTitle>Submit a complaint</DialogTitle></DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Title</label>
              <input type="text" value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                data-testid="complaint-title-input"
                className="input-field" placeholder="Brief description of the issue" required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Category</label>
                <select value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  data-testid="complaint-category-select"
                  className="input-field">
                  <option value="plumbing">Plumbing</option>
                  <option value="electrical">Electrical</option>
                  <option value="sanitation">Sanitation</option>
                  <option value="parking">Parking</option>
                  <option value="security">Security</option>
                  <option value="general">General</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Priority</label>
                <select value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                  data-testid="complaint-priority-select"
                  className="input-field">
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-[11px] uppercase tracking-wider font-medium mb-1.5" style={{ color: '#5F5E5A' }}>Description</label>
              <textarea value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                data-testid="complaint-description-input"
                className="input-field"
                style={{ minHeight: 110, padding: '10px 12px', height: 'auto' }}
                placeholder="What happened? When? Any details?" required />
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowModal(false)} className="btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} data-testid="submit-complaint-btn" className="btn-primary disabled:opacity-50">
                {saving ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="card max-w-2xl">
          {detail && (
            <ComplaintDetailView
              complaint={detail}
              canManage={canManage}
              onStatusUpdate={(s) => handleStatusUpdate(detail.id, s)}
              onClose={() => setDetail(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

const FilterChip = ({ active, onClick, count, children, testid }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className="px-3 py-1.5 rounded-full text-[12px] font-medium transition-all flex items-center gap-1.5 whitespace-nowrap"
    style={
      active
        ? { backgroundColor: 'var(--accent-raw)', color: '#FFFFFF' }
        : { backgroundColor: '#F1EFE8', color: '#5F5E5A', border: '0.5px solid rgba(0,0,0,0.06)' }
    }
  >
    {children}
    <span
      className="rounded-full px-1.5 text-[10px]"
      style={
        active
          ? { backgroundColor: 'rgba(255,255,255,0.25)', color: '#FFFFFF' }
          : { backgroundColor: '#FFFFFF', color: '#5F5E5A' }
      }
    >
      {count}
    </span>
  </button>
);

const priorityBadge = (p) => {
  const map = {
    urgent: 'badge-danger',
    high: 'badge-warning',
    medium: 'badge-info',
    low: 'badge-success',
  };
  return <span className={map[p] || 'badge-neutral'}>{p}</span>;
};

const statusBadge = (s) => {
  if (s === 'resolved' || s === 'closed') return <span className="badge-success">{s.replace('_', ' ')}</span>;
  if (s === 'in_progress') return <span className="badge-warning">In progress</span>;
  if (s === 'open') return <span className="badge-danger">Open</span>;
  return <span className="badge-neutral">{s}</span>;
};

const ComplaintCard = ({ complaint, onClick }) => (
  <button
    onClick={onClick}
    data-testid={`complaint-card-${complaint.id}`}
    className="card p-4 text-left hover:shadow-card-hover transition-shadow"
  >
    <div className="flex items-start justify-between gap-2 mb-2">
      <h2 className="flex-1 leading-snug">{complaint.title}</h2>
      {priorityBadge(complaint.priority)}
    </div>
    <p className="text-[12px] mb-3 line-clamp-2" style={{ color: '#5F5E5A' }}>
      {complaint.description}
    </p>
    <div className="flex items-center justify-between gap-2 text-[11px]">
      <div className="flex items-center gap-2 flex-wrap">
        {statusBadge(complaint.status)}
        <span className="badge-neutral capitalize">{complaint.category}</span>
      </div>
      <span style={{ color: '#888780' }} className="flex items-center gap-1 whitespace-nowrap">
        <Clock className="w-3 h-3" /> {timeAgo(complaint.created_at)}
      </span>
    </div>
  </button>
);

const ComplaintDetailView = ({ complaint, canManage, onStatusUpdate, onClose }) => (
  <div data-testid="complaint-detail">
    <DialogHeader>
      <DialogTitle className="pr-6">{complaint.title}</DialogTitle>
    </DialogHeader>
    <div className="space-y-4 mt-2">
      {/* Badges */}
      <div className="flex flex-wrap gap-2">
        {statusBadge(complaint.status)}
        {priorityBadge(complaint.priority)}
        <span className="badge-neutral capitalize flex items-center gap-1">
          <Tag className="w-3 h-3" /> {complaint.category}
        </span>
      </div>

      {/* Description */}
      <div className="card-surface p-4">
        <p className="text-[11px] uppercase tracking-wider font-medium mb-2" style={{ color: '#5F5E5A' }}>Description</p>
        <p className="text-[13px] whitespace-pre-wrap" style={{ color: '#1A1A18', lineHeight: 1.55 }}>
          {complaint.description}
        </p>
      </div>

      {/* Meta */}
      <div className="grid grid-cols-2 gap-3 text-[12px]">
        <div>
          <p className="text-[11px] uppercase tracking-wider font-medium" style={{ color: '#5F5E5A' }}>Filed</p>
          <p className="mt-1 flex items-center gap-1" style={{ color: '#1A1A18' }}>
            <Calendar className="w-3.5 h-3.5" />
            {new Date(complaint.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
          </p>
        </div>
        {complaint.updated_at && (
          <div>
            <p className="text-[11px] uppercase tracking-wider font-medium" style={{ color: '#5F5E5A' }}>Updated</p>
            <p className="mt-1" style={{ color: '#1A1A18' }}>{timeAgo(complaint.updated_at)}</p>
          </div>
        )}
      </div>

      {canManage && (
        <div className="card-surface p-4">
          <p className="text-[11px] uppercase tracking-wider font-medium mb-2" style={{ color: '#5F5E5A' }}>Update status</p>
          <div className="flex flex-wrap gap-2">
            {['open', 'in_progress', 'resolved', 'closed'].map((s) => (
              <button
                key={s}
                onClick={() => onStatusUpdate(s)}
                data-testid={`detail-status-${s}`}
                disabled={s === complaint.status}
                className="px-3 py-1.5 rounded-full text-[12px] font-medium transition-all"
                style={
                  s === complaint.status
                    ? { backgroundColor: 'var(--accent-raw)', color: '#FFFFFF', cursor: 'default' }
                    : { backgroundColor: '#FFFFFF', color: '#1A1A18', border: '0.5px solid rgba(0,0,0,0.10)' }
                }
              >
                {s === complaint.status && <CheckCircle2 className="w-3.5 h-3.5 inline mr-1" />}
                {s.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex justify-end pt-2">
        <button onClick={onClose} className="btn-secondary" data-testid="close-detail-btn">Close</button>
      </div>
    </div>
  </div>
);

// ============== Haat Bazaar ==============
const BazaarPage = () => {
  const [link, setLink] = useState(null);
  const [wallet, setWallet] = useState({ balance: 0 });
  const [bazaarStatus, setBazaarStatus] = useState({ connected: false });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [linkRes, walletRes, statusRes] = await Promise.all([
          miscAPI.getBazaarLink().catch(() => ({ data: { available: false } })),
          maintenanceAPI.getWallet().catch(() => ({ data: { balance: 0 } })),
          maintenanceAPI.getBazaarStatus().catch(() => ({ data: { connected: false } })),
        ]);
        setLink(linkRes.data);
        setWallet(walletRes.data);
        setBazaarStatus(statusRes.data);
      } catch (e) {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-elevated rounded w-48" />
        <div className="h-64 bg-bg-elevated rounded-xl" />
      </div>
    );
  }

  const available = link?.available || bazaarStatus.connected;

  return (
    <div data-testid="bazaar-page" className="space-y-6">
      <div>
        <h1>Haat Bazaar</h1>
        <p className="text-[12px]" style={{ color: '#5F5E5A' }}>Spend your reward points</p>
      </div>

      {/* Hero */}
      <div
        className="rounded-xl p-6 sm:p-8 relative overflow-hidden"
        style={{ backgroundColor: 'var(--accent-light)', border: '0.5px solid rgba(0,0,0,0.06)' }}
        data-testid="bazaar-hero"
      >
        <div className="absolute -right-6 -bottom-6 opacity-10" aria-hidden="true">
          <ShoppingBag className="w-40 h-40" style={{ color: 'var(--accent-raw)' }} />
        </div>
        <div className="relative">
          <div className="flex items-center gap-2 mb-2">
            <span
              className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-wider font-medium flex items-center gap-1"
              style={{
                backgroundColor: available ? '#EAF3DE' : '#FAEEDA',
                color: available ? '#3B6D11' : '#854F0B',
              }}
            >
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: available ? '#3B6D11' : '#854F0B' }}
              />
              {available ? 'Connected' : 'Coming soon'}
            </span>
          </div>
          <h2 className="!text-[22px]" style={{ color: '#1A1A18' }}>
            {available ? 'Shop with your points' : 'Bazaar setup in progress'}
          </h2>
          <p className="text-[13px] mt-1 max-w-md" style={{ color: '#5F5E5A' }}>
            {available
              ? 'Convert maintenance reward points into shopping at our partner store. 1 point = ₹1 value.'
              : 'Once your platform admin connects the bazaar service you will be able to redeem points here.'}
          </p>

          {/* Balance display */}
          <div className="mt-5 flex items-center gap-3 flex-wrap">
            <div
              className="flex items-center gap-2 rounded-lg px-4 py-2.5"
              style={{ backgroundColor: '#FFFFFF', border: '0.5px solid rgba(0,0,0,0.06)' }}
            >
              <Wallet className="w-4 h-4" style={{ color: 'var(--accent-raw)' }} />
              <div>
                <div className="text-[10px] uppercase tracking-wider font-medium" style={{ color: '#5F5E5A' }}>
                  Balance
                </div>
                <div className="text-[18px] font-medium leading-tight" style={{ color: '#1A1A18' }}>
                  {wallet.balance} <span className="text-[12px]" style={{ color: '#5F5E5A' }}>pts</span>
                </div>
              </div>
            </div>

            {available && link?.shopping_link && (
              <a
                href={link.shopping_link}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="bazaar-link"
                className="btn-primary inline-flex items-center gap-2"
              >
                Visit Bazaar <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* How it works */}
      <div className="card p-5 sm:p-6">
        <h2 className="mb-4">How it works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <BazaarStep n="1" icon={CheckCircle2} text="Pay your maintenance bill on time" />
          <BazaarStep n="2" icon={Sparkles} text="Earn 1 point for every ₹1 paid (verified)" />
          <BazaarStep n="3" icon={ArrowRight} text="Spend points at our partner Bazaar" />
        </div>
      </div>
    </div>
  );
};

const BazaarStep = ({ n, icon: Icon, text }) => (
  <div className="flex items-start gap-3">
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-medium"
      style={{ backgroundColor: 'var(--accent-light)', color: 'var(--accent-raw)' }}
    >
      {n}
    </div>
    <div className="flex-1">
      <Icon className="w-4 h-4 mb-1" style={{ color: 'var(--accent-raw)' }} />
      <p className="text-[12px]" style={{ color: '#1A1A18', lineHeight: 1.5 }}>{text}</p>
    </div>
  </div>
);

export { NoticesPage, ComplaintsPage, BazaarPage };
