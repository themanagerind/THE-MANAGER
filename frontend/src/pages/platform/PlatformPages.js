import { useState, useEffect } from 'react';
import { Building2, Users, ShieldCheck, Link as LinkIcon, ExternalLink, Wifi, WifiOff, Key, Globe } from 'lucide-react';
import { platformAPI } from '../../lib/api';
import { toast } from 'sonner';

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
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-4">Admin</th>
                <th className="text-left p-4">Society</th>
                <th className="text-left p-4">Mobile</th>
                <th className="text-left p-4">Status</th>
                <th className="text-left p-4">Actions</th>
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
                    <td className="p-4">
                      <p className="font-medium text-text-primary">{admin.name}</p>
                      <p className="text-sm text-text-secondary">{admin.email}</p>
                    </td>
                    <td className="p-4">
                      <p className="font-medium text-text-primary">{admin.society?.name || '-'}</p>
                      <p className="text-sm text-text-secondary truncate max-w-[200px]">{admin.society?.address || '-'}</p>
                    </td>
                    <td className="p-4 text-text-primary">{admin.mobile}</td>
                    <td className="p-4">{getStatusBadge(admin.status)}</td>
                    <td className="p-4">
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

export { PlatformDashboard, ManageAdmins, BazaarSettings };
