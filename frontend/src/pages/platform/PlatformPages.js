import { useState, useEffect } from 'react';
import { Building2, Users, ShieldCheck, ShieldX, Link as LinkIcon, ExternalLink } from 'lucide-react';
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
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-bg-surface rounded-xl" />
          ))}
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

  useEffect(() => {
    fetchAdmins();
  }, []);

  const handleApprove = async (adminId) => {
    try {
      await platformAPI.approveAdmin(adminId);
      toast.success('Admin approved');
      fetchAdmins();
    } catch (e) {
      toast.error('Failed to approve admin');
    }
  };

  const handleBlock = async (adminId) => {
    try {
      await platformAPI.blockAdmin(adminId);
      toast.success('Admin blocked');
      fetchAdmins();
    } catch (e) {
      toast.error('Failed to block admin');
    }
  };

  const handleUnblock = async (adminId) => {
    try {
      await platformAPI.unblockAdmin(adminId);
      toast.success('Admin unblocked');
      fetchAdmins();
    } catch (e) {
      toast.error('Failed to unblock admin');
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <span className="badge-success">Active</span>;
      case 'pending':
        return <span className="badge-warning">Pending</span>;
      case 'blocked':
        return <span className="badge-danger">Blocked</span>;
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
                <tr>
                  <td colSpan={5} className="p-8 text-center text-text-secondary">
                    <Users className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No admins found</p>
                  </td>
                </tr>
              ) : (
                admins.map((admin) => (
                  <tr key={admin.id} className="table-row">
                    <td className="p-4">
                      <div>
                        <p className="font-medium text-text-primary">{admin.name}</p>
                        <p className="text-sm text-text-secondary">{admin.email}</p>
                      </div>
                    </td>
                    <td className="p-4">
                      <div>
                        <p className="font-medium text-text-primary">{admin.society?.name || '-'}</p>
                        <p className="text-sm text-text-secondary truncate max-w-[200px]">
                          {admin.society?.address || '-'}
                        </p>
                      </div>
                    </td>
                    <td className="p-4 text-text-primary">{admin.mobile}</td>
                    <td className="p-4">{getStatusBadge(admin.status)}</td>
                    <td className="p-4">
                      <div className="flex gap-2">
                        {admin.status === 'pending' && (
                          <button
                            onClick={() => handleApprove(admin.id)}
                            data-testid={`approve-admin-${admin.id}`}
                            className="px-3 py-1 bg-success/20 text-success rounded-lg text-sm font-medium hover:bg-success/30 transition-colors"
                          >
                            Approve
                          </button>
                        )}
                        {admin.status === 'active' && (
                          <button
                            onClick={() => handleBlock(admin.id)}
                            data-testid={`block-admin-${admin.id}`}
                            className="px-3 py-1 bg-danger/20 text-danger rounded-lg text-sm font-medium hover:bg-danger/30 transition-colors"
                          >
                            Block
                          </button>
                        )}
                        {admin.status === 'blocked' && (
                          <button
                            onClick={() => handleUnblock(admin.id)}
                            data-testid={`unblock-admin-${admin.id}`}
                            className="px-3 py-1 bg-info/20 text-info rounded-lg text-sm font-medium hover:bg-info/30 transition-colors"
                          >
                            Unblock
                          </button>
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
  const [link, setLink] = useState('');
  const [currentLink, setCurrentLink] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const fetchLink = async () => {
      try {
        const res = await platformAPI.getShoppingLink();
        setCurrentLink(res.data.shopping_link || '');
        setLink(res.data.shopping_link || '');
      } catch (e) {
        toast.error('Failed to load shopping link');
      } finally {
        setLoading(false);
      }
    };
    fetchLink();
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await platformAPI.setShoppingLink(link);
      setCurrentLink(link);
      toast.success('Shopping link updated');
    } catch (e) {
      toast.error('Failed to update link');
    } finally {
      setSaving(false);
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
        <p className="text-text-secondary mt-1">Configure the shopping link for wallet redemption</p>
      </div>

      <div className="card p-6 max-w-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 bg-accent/20 rounded-lg">
            <LinkIcon className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">Shopping Link</h3>
            <p className="text-sm text-text-secondary">
              This URL will be used for wallet redemption across all societies
            </p>
          </div>
        </div>

        {currentLink && (
          <div className="mb-6 p-4 bg-bg-elevated rounded-lg flex items-center justify-between">
            <div className="flex items-center gap-2 text-text-secondary">
              <span className="text-sm">Current link:</span>
              <span className="text-accent truncate max-w-[300px]">{currentLink}</span>
            </div>
            <a
              href={currentLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent-hover"
            >
              <ExternalLink className="w-5 h-5" />
            </a>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Shopping URL
            </label>
            <input
              type="url"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              data-testid="shopping-link-input"
              className="input-field w-full"
              placeholder="https://example.com/shop"
              required
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            data-testid="save-shopping-link-btn"
            className="btn-primary disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Link'}
          </button>
        </form>
      </div>
    </div>
  );
};

export { PlatformDashboard, ManageAdmins, BazaarSettings };
