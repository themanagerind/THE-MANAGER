import { useState, useEffect } from 'react';
import { Building2, Users, ShieldCheck, Link as LinkIcon, ExternalLink, Wifi, WifiOff, Key, Globe, Plus, MapPin, Phone, Lock, Eye, EyeOff, Pencil, Trash2, Navigation } from 'lucide-react';
import { platformAPI } from '../../lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/alert-dialog';
import { LocationPicker } from '../../components/LocationPicker';

const PlatformDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await platformAPI.getStats();
        setStats(res.data);
      } catch (e) {
        toast.error('Failed to load stats');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-bg-surface rounded-xl" />)}
        </div>
      </div>
    );
  }

  const statCards = [
    { label: 'Total Societies', value: stats?.total_societies || 0, icon: Building2, color: 'text-accent' },
    { label: 'Active Societies', value: stats?.active_societies || 0, icon: ShieldCheck, color: 'text-success' },
    { label: 'Pending Admins', value: stats?.pending_admins || 0, icon: Users, color: 'text-warning' },
    { label: 'Total Residents', value: stats?.total_residents || 0, icon: Users, color: 'text-info' },
  ];

  return (
    <div data-testid="platform-dashboard" className="space-y-8">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Platform Dashboard</h1>
        <p className="text-text-secondary mt-1">Manage all societies and admins</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {statCards.map((stat, i) => (
          <div key={i} className="stat-card" data-testid={`platform-stat-${i}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="stat-label">{stat.label}</p>
                <p className="stat-value">{stat.value}</p>
              </div>
              <div className={`p-2 rounded-lg ${stat.color}`} style={{ backgroundColor: 'var(--accent-light)' }}>
                <stat.icon className="w-5 h-5" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const ManageSocieties = () => {
  const [societies, setSocieties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    society_name: '', society_address: '', society_location: '', latitude: null, longitude: null,
    admin_name: '', admin_mobile: '', admin_password: ''
  });
  const [editSociety, setEditSociety] = useState(null);
  const [editData, setEditData] = useState({ society_name: '', society_address: '', society_location: '', latitude: null, longitude: null });
  const [deleteSociety, setDeleteSociety] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const fetchSocieties = async () => {
    try {
      const res = await platformAPI.getSocieties();
      setSocieties(res.data);
    } catch (e) {
      toast.error('Failed to load societies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSocieties(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!formData.society_name || !formData.society_address || !formData.society_location || !formData.admin_name || !formData.admin_mobile || !formData.admin_password) {
      toast.error('All fields are required');
      return;
    }
    setSaving(true);
    try {
      await platformAPI.createSociety(formData);
      toast.success(`Society '${formData.society_name}' created successfully!`);
      setShowAddModal(false);
      setFormData({ society_name: '', society_address: '', society_location: '', latitude: null, longitude: null, admin_name: '', admin_mobile: '', admin_password: '' });
      fetchSocieties();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create society');
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (soc) => {
    setEditSociety(soc);
    setEditData({
      society_name: soc.name, society_address: soc.address, society_location: soc.location || '',
      latitude: soc.latitude || null, longitude: soc.longitude || null
    });
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    if (!editData.society_name || !editData.society_address || !editData.society_location) {
      toast.error('All fields are required');
      return;
    }
    setSaving(true);
    try {
      await platformAPI.updateSociety(editSociety.id, editData);
      toast.success('Society updated successfully');
      setEditSociety(null);
      fetchSocieties();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to update society');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await platformAPI.deleteSociety(deleteSociety.id);
      toast.success(`Society '${deleteSociety.name}' deleted`);
      setDeleteSociety(null);
      fetchSocieties();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete society');
    } finally {
      setDeleting(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active': return <span className="badge-success">Active</span>;
      case 'blocked': return <span className="badge-danger">Blocked</span>;
      default: return <span className="badge-info">{status}</span>;
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
    <div data-testid="manage-societies-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Manage Societies</h1>
          <p className="text-text-secondary mt-1">Create and manage housing societies</p>
        </div>
        <button onClick={() => setShowAddModal(true)} data-testid="add-society-btn"
          className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center">
          <Plus className="w-4 h-4" /> Add Society
        </button>
      </div>

      {/* Societies List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {societies.length === 0 ? (
          <div className="col-span-full card p-12 text-center">
            <Building2 className="w-16 h-16 mx-auto mb-4 text-text-muted opacity-50" />
            <p className="text-text-secondary text-lg">No societies yet</p>
            <p className="text-text-muted text-sm mt-1">Click "Add Society" to create the first one</p>
          </div>
        ) : societies.map((soc) => (
          <div key={soc.id} className="card p-6 hover:border-accent/30 transition-colors">
            <div className="flex items-start justify-between mb-4">
              <div className="p-3 bg-accent/20 rounded-lg">
                <Building2 className="w-6 h-6 text-accent" />
              </div>
              {getStatusBadge(soc.status)}
            </div>
            <h3 className="font-semibold text-text-primary text-lg mb-1">{soc.name}</h3>
            <div className="flex items-center gap-1 text-text-secondary text-sm mb-1">
              <MapPin className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{soc.address}</span>
            </div>
            {soc.location && (
              <div className="flex items-center gap-1 text-text-secondary text-sm mb-4">
                <Navigation className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{soc.location}</span>
              </div>
            )}
            {soc.admin ? (
              <div className="pt-4 border-t border-border-color">
                <p className="text-text-muted text-xs mb-1">Admin</p>
                <div className="flex items-center justify-between">
                  <span className="text-text-primary text-sm font-medium">{soc.admin.name}</span>
                  <span className="text-text-secondary text-xs">{soc.admin.mobile}</span>
                </div>
              </div>
            ) : (
              <div className="pt-4 border-t border-border-color">
                <p className="text-text-muted text-sm">No admin assigned</p>
              </div>
            )}
            <div className="flex gap-2 mt-4 pt-4 border-t border-border-color">
              <button onClick={() => openEdit(soc)} data-testid={`edit-society-${soc.id}`}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-accent/10 text-accent rounded-lg text-sm font-medium hover:bg-accent/20 transition-colors">
                <Pencil className="w-3.5 h-3.5" /> Edit
              </button>
              <button onClick={() => setDeleteSociety(soc)} data-testid={`delete-society-${soc.id}`}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-danger/10 text-danger rounded-lg text-sm font-medium hover:bg-danger/20 transition-colors">
                <Trash2 className="w-3.5 h-3.5" /> Remove
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Society Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="bg-bg-surface border-border-color sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="text-text-primary text-xl">Add New Society</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4 mt-2">
            <div className="p-3 bg-bg-elevated rounded-lg mb-2">
              <p className="text-accent text-sm font-medium">Society Details</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Name</label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={formData.society_name}
                  onChange={(e) => setFormData({ ...formData, society_name: e.target.value })}
                  data-testid="society-name-input"
                  className="input-field w-full pl-10" placeholder="e.g. Green Valley Apartments" required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Address</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={formData.society_address}
                  onChange={(e) => setFormData({ ...formData, society_address: e.target.value })}
                  data-testid="society-address-input"
                  className="input-field w-full pl-10" placeholder="Full address" required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Location (GPS ya Search)</label>
              <LocationPicker
                value={formData.society_location}
                onChange={({ address, lat, lng }) => setFormData(f => ({ ...f, society_location: address, latitude: lat, longitude: lng }))}
                testIdPrefix="society-location" />
            </div>

            <div className="p-3 bg-bg-elevated rounded-lg">
              <p className="text-accent text-sm font-medium">Admin Details</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Admin Name</label>
              <div className="relative">
                <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={formData.admin_name}
                  onChange={(e) => setFormData({ ...formData, admin_name: e.target.value })}
                  data-testid="admin-name-input"
                  className="input-field w-full pl-10" placeholder="Admin full name" required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Admin Mobile</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={formData.admin_mobile}
                  onChange={(e) => setFormData({ ...formData, admin_mobile: e.target.value.replace(/\D/g, '').slice(0, 10) })}
                  data-testid="admin-mobile-input"
                  className="input-field w-full pl-10" placeholder="10-digit mobile" maxLength={10} required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Admin Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type={showPassword ? 'text' : 'password'} value={formData.admin_password}
                  onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                  data-testid="admin-password-input"
                  className="input-field w-full pl-10 pr-10" placeholder="Set admin password" required />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex gap-3 justify-end pt-2">
              <button type="button" onClick={() => setShowAddModal(false)} className="btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} data-testid="create-society-btn"
                className="btn-primary disabled:opacity-50 flex items-center gap-2">
                {saving ? 'Creating...' : <><Plus className="w-4 h-4" /> Create Society</>}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Edit Society Modal */}
      <Dialog open={!!editSociety} onOpenChange={(open) => !open && setEditSociety(null)}>
        <DialogContent className="bg-bg-surface border-border-color sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="text-text-primary text-xl">Edit Society</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleUpdate} className="space-y-4 mt-2">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Name</label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={editData.society_name}
                  onChange={(e) => setEditData({ ...editData, society_name: e.target.value })}
                  data-testid="edit-society-name-input"
                  className="input-field w-full pl-10" placeholder="Society name" required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Address</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input type="text" value={editData.society_address}
                  onChange={(e) => setEditData({ ...editData, society_address: e.target.value })}
                  data-testid="edit-society-address-input"
                  className="input-field w-full pl-10" placeholder="Full address" required />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Location (GPS ya Search)</label>
              <LocationPicker
                value={editData.society_location}
                onChange={({ address, lat, lng }) => setEditData(d => ({ ...d, society_location: address, latitude: lat, longitude: lng }))}
                testIdPrefix="edit-society-location" />
            </div>
            <div className="flex gap-3 justify-end pt-2">
              <button type="button" onClick={() => setEditSociety(null)} className="btn-secondary">Cancel</button>
              <button type="submit" disabled={saving} data-testid="update-society-btn"
                className="btn-primary disabled:opacity-50">
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteSociety} onOpenChange={(open) => !open && setDeleteSociety(null)}>
        <AlertDialogContent className="bg-bg-surface border-border-color">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-text-primary">Remove Society?</AlertDialogTitle>
            <AlertDialogDescription className="text-text-secondary">
              Are you sure you want to remove <span className="font-semibold text-text-primary">"{deleteSociety?.name}"</span>?
              This will permanently delete the society along with its admin, wings, flats and residents. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-society-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={deleting} data-testid="confirm-delete-society-btn"
              className="bg-danger text-white hover:bg-danger/90">
              {deleting ? 'Removing...' : 'Yes, Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

const ManageAdmins = () => {
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAdmins = async () => {
    try {
      const res = await platformAPI.getAdmins();
      setAdmins(res.data);
    } catch (e) {
      toast.error('Failed to load admins');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAdmins(); }, []);

  const handleApprove = async (adminId) => {
    try { await platformAPI.approveAdmin(adminId); toast.success('Admin approved'); fetchAdmins(); }
    catch (e) { toast.error('Failed to approve admin'); }
  };
  const handleBlock = async (adminId) => {
    try { await platformAPI.blockAdmin(adminId); toast.success('Admin blocked'); fetchAdmins(); }
    catch (e) { toast.error('Failed to block admin'); }
  };
  const handleUnblock = async (adminId) => {
    try { await platformAPI.unblockAdmin(adminId); toast.success('Admin unblocked'); fetchAdmins(); }
    catch (e) { toast.error('Failed to unblock admin'); }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active': return <span className="badge-success">Active</span>;
      case 'pending': return <span className="badge-warning">Pending</span>;
      case 'blocked': return <span className="badge-danger">Blocked</span>;
      default: return <span className="badge-info">{status}</span>;
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
    <div data-testid="manage-admins-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Manage Admins</h1>
        <p className="text-text-secondary mt-1">Approve or block society admins</p>
      </div>
      <div className="card overflow-hidden">
        <div className="table-mobile-wrapper">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-3 sm:p-4">Admin</th>
                <th className="text-left p-3 sm:p-4">Society</th>
                <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Mobile</th>
                <th className="text-left p-3 sm:p-4">Status</th>
                <th className="text-left p-3 sm:p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {admins.length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-text-secondary">
                  <Users className="w-12 h-12 mx-auto mb-2 opacity-50" /><p>No admins found</p>
                </td></tr>
              ) : (
                admins.map((admin) => (
                  <tr key={admin.id} className="table-row">
                    <td className="p-3 sm:p-4">
                      <p className="font-medium text-text-primary text-sm">{admin.name}</p>
                      <p className="text-xs text-text-secondary">{admin.email}</p>
                    </td>
                    <td className="p-3 sm:p-4">
                      <p className="font-medium text-text-primary text-sm">{admin.society?.name || '-'}</p>
                      <p className="text-xs text-text-secondary truncate max-w-[120px] sm:max-w-[200px]">{admin.society?.address || '-'}</p>
                    </td>
                    <td className="p-3 sm:p-4 text-text-primary hidden sm:table-cell">{admin.mobile}</td>
                    <td className="p-3 sm:p-4">{getStatusBadge(admin.status)}</td>
                    <td className="p-3 sm:p-4">
                      <div className="flex gap-2">
                        {admin.status === 'pending' && (
                          <button onClick={() => handleApprove(admin.id)} data-testid={`approve-admin-${admin.id}`}
                            className="px-3 py-1 bg-success/20 text-success rounded-lg text-sm font-medium hover:bg-success/30 transition-colors">Approve</button>
                        )}
                        {admin.status === 'active' && (
                          <button onClick={() => handleBlock(admin.id)} data-testid={`block-admin-${admin.id}`}
                            className="px-3 py-1 bg-danger/20 text-danger rounded-lg text-sm font-medium hover:bg-danger/30 transition-colors">Block</button>
                        )}
                        {admin.status === 'blocked' && (
                          <button onClick={() => handleUnblock(admin.id)} data-testid={`unblock-admin-${admin.id}`}
                            className="px-3 py-1 bg-info/20 text-info rounded-lg text-sm font-medium hover:bg-info/30 transition-colors">Unblock</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const BazaarSettings = () => {
  const [settings, setSettings] = useState({
    bazaar_api_url: '',
    bazaar_secret_key: '',
    bazaar_connected: false,
    shopping_link: ''
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savingLink, setSavingLink] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await platformAPI.getBazaarSettings();
        setSettings({
          bazaar_api_url: res.data.bazaar_api_url || '',
          bazaar_secret_key: res.data.bazaar_secret_key || '',
          bazaar_connected: res.data.bazaar_connected || false,
          shopping_link: res.data.shopping_link || ''
        });
      } catch (e) {
        toast.error('Failed to load settings');
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSaveBazaar = async (e) => {
    e.preventDefault();
    if (!settings.bazaar_api_url || !settings.bazaar_secret_key) {
      toast.error('Both API URL and Secret Key are required');
      return;
    }
    setSaving(true);
    try {
      await platformAPI.updateBazaarSettings({
        bazaar_api_url: settings.bazaar_api_url,
        bazaar_secret_key: settings.bazaar_secret_key
      });
      setSettings(s => ({ ...s, bazaar_connected: true }));
      toast.success('Bazaar settings saved! Redeem buttons are now active.');
    } catch (e) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveLink = async (e) => {
    e.preventDefault();
    setSavingLink(true);
    try {
      await platformAPI.setShoppingLink(settings.shopping_link);
      toast.success('Shopping link updated');
    } catch (e) {
      toast.error('Failed to update link');
    } finally {
      setSavingLink(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-64 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="bazaar-settings-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Bazaar Settings</h1>
        <p className="text-text-secondary mt-1">Configure the shopping platform integration</p>
      </div>

      {/* Connection Status */}
      <div className="card p-6 max-w-2xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {settings.bazaar_connected ? (
              <div className="p-3 bg-success/20 rounded-lg"><Wifi className="w-6 h-6 text-success" /></div>
            ) : (
              <div className="p-3 bg-danger/20 rounded-lg"><WifiOff className="w-6 h-6 text-danger" /></div>
            )}
            <div>
              <h3 className="font-semibold text-text-primary">Connection Status</h3>
              <p className={`text-sm font-medium ${settings.bazaar_connected ? 'text-success' : 'text-danger'}`}>
                {settings.bazaar_connected ? 'Connected' : 'Not Connected'}
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSaveBazaar} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              <Globe className="w-4 h-4 inline mr-1" /> Shopping Platform API URL
            </label>
            <input type="url" value={settings.bazaar_api_url}
              onChange={(e) => setSettings({ ...settings, bazaar_api_url: e.target.value })}
              data-testid="bazaar-api-url-input"
              className="input-field w-full" placeholder="https://bazaar.com/api" required />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              <Key className="w-4 h-4 inline mr-1" /> Shopping Platform Secret Key
            </label>
            <div className="relative">
              <input type={showKey ? 'text' : 'password'} value={settings.bazaar_secret_key}
                onChange={(e) => setSettings({ ...settings, bazaar_secret_key: e.target.value })}
                data-testid="bazaar-secret-key-input"
                className="input-field w-full pr-20" placeholder="Enter secret key" required />
              <button type="button" onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary text-xs">
                {showKey ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>
          <button type="submit" disabled={saving} data-testid="save-bazaar-settings-btn"
            className="btn-primary disabled:opacity-50">
            {saving ? 'Saving...' : 'Save & Connect'}
          </button>
        </form>
      </div>

      {/* Shopping Link */}
      <div className="card p-6 max-w-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 bg-accent/20 rounded-lg"><LinkIcon className="w-6 h-6 text-accent" /></div>
          <div>
            <h3 className="font-semibold text-text-primary">Shopping Redirect URL</h3>
            <p className="text-sm text-text-secondary">Where users go after redeeming points</p>
          </div>
        </div>

        {settings.shopping_link && (
          <div className="mb-4 p-4 bg-bg-elevated rounded-lg flex items-center justify-between">
            <span className="text-accent truncate max-w-[300px]">{settings.shopping_link}</span>
            <a href={settings.shopping_link} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-hover">
              <ExternalLink className="w-5 h-5" />
            </a>
          </div>
        )}

        <form onSubmit={handleSaveLink} className="space-y-4">
          <input type="url" value={settings.shopping_link}
            onChange={(e) => setSettings({ ...settings, shopping_link: e.target.value })}
            data-testid="shopping-link-input"
            className="input-field w-full" placeholder="https://bazaar.com/shop" required />
          <button type="submit" disabled={savingLink} data-testid="save-shopping-link-btn"
            className="btn-primary disabled:opacity-50">
            {savingLink ? 'Saving...' : 'Save Link'}
          </button>
        </form>
      </div>
    </div>
  );
};

export { PlatformDashboard, ManageAdmins, ManageSocieties, BazaarSettings };
