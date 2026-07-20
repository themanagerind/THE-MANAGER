import { useState, useEffect } from 'react';
import { Building2, Home, Users, Receipt, TrendingUp, Clock, CheckCircle, XCircle, Edit2, ChevronDown } from 'lucide-react';
import { adminAPI, maintenanceAPI, authAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { ConfirmDialog } from '../../components/ConfirmDialogs';

const AdminDashboard = () => {
  const { user, switchRole } = useAuthStore();
  const navigate = useNavigate();
  const [roles, setRoles] = useState([]);
  const [showRoleSwitch, setShowRoleSwitch] = useState(false);
  const [stats, setStats] = useState({
    wings: 0,
    flats: 0,
    residents: 0,
    pendingResidents: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [wingsRes, flatsRes, residentsRes, pendingRes] = await Promise.all([
          adminAPI.getWings(),
          adminAPI.getFlats(),
          adminAPI.getResidents(),
          adminAPI.getResidents('pending'),
        ]);
        
        setStats({
          wings: wingsRes.data.length,
          flats: flatsRes.data.length,
          residents: residentsRes.data.length,
          pendingResidents: pendingRes.data.length,
        });
      } catch (e) {
        console.error('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    // fetch available roles for quick switch
    const fetchRoles = async () => {
      try {
        const res = await authAPI.getRoles();
        setRoles(res.data);
      } catch (e) {
        // ignore
      }
    };
    fetchRoles();
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
    { label: 'Total Wings', value: stats.wings, icon: Building2, color: 'text-accent' },
    { label: 'Total Flats', value: stats.flats, icon: Home, color: 'text-info' },
    { label: 'Total Residents', value: stats.residents, icon: Users, color: 'text-success' },
    { label: 'Pending Approvals', value: stats.pendingResidents, icon: Clock, color: 'text-warning' },
  ];

  return (
    <div data-testid="admin-dashboard" className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Admin Dashboard</h1>
          <p className="text-text-secondary mt-1">Welcome back, {user?.name}</p>
        </div>
        {roles.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setShowRoleSwitch(!showRoleSwitch)}
              data-testid="admin-role-switch-btn"
              className="btn-secondary flex items-center gap-2"
            >
              Switch Role <ChevronDown className="w-4 h-4" />
            </button>
            {showRoleSwitch && (
              <div className="absolute right-0 mt-2 w-44 card p-2">
                {roles.filter(r => r.role !== user?.role).map((r) => (
                  <button
                    key={r.role}
                    onClick={async () => {
                      try {
                        const res = await authAPI.switchRole(r.role);
                        switchRole(res.data.user, res.data.access_token);
                        setShowRoleSwitch(false);
                        // navigate to appropriate dashboard
                        switch (r.role) {
                          case 'platform_owner': navigate('/platform'); break;
                          case 'admin': navigate('/admin'); break;
                          case 'sub_admin': navigate('/subadmin'); break;
                          case 'resident': navigate('/resident'); break;
                          default: navigate('/');
                        }
                      } catch (e) {
                        toast.error('Failed to switch role');
                      }
                    }}
                    data-testid={`admin-switch-to-${r.role}`}
                    className="w-full text-left px-3 py-2 hover:bg-bg-elevated rounded"
                  >
                    {r.role.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {statCards.map((stat, i) => (
          <div key={i} className="stat-card" data-testid={`admin-stat-${i}`}>
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

const WingsManager = () => {
  const [wings, setWings] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchWings = async () => {
    try {
      const res = await adminAPI.getWings();
      setWings(res.data);
    } catch (e) {
      toast.error('Failed to load wings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWings();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-40 bg-bg-surface rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="wings-manager-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Wings</h1>
          <p className="text-text-secondary mt-1">View-only wing list (only Platform Owner can add/edit/remove)</p>
        </div>
      </div>

      {wings.length === 0 ? (
        <div className="card p-12 text-center">
          <Building2 className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Wings Yet</h3>
          <p className="text-text-secondary mb-4">Only Platform Owner can create wings</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {wings.map((wing) => (
            <div key={wing.id} className="card p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-accent/20 rounded-lg">
                  <Building2 className="w-6 h-6 text-accent" />
                </div>
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">{wing.name}</h3>
              <p className="text-text-secondary text-sm">
                Sub-Admin: {wing.sub_admin_name || 'Not assigned'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const FlatMapping = () => {
  const [mapping, setMapping] = useState([]);
  const [loading, setLoading] = useState(true);

  const parseWingName = (value) => {
    const raw = (value || '').trim().toUpperCase();
    const match = raw.match(/^([A-Z]+)(\d+)?$/);
    if (match) {
      return {
        prefix: match[1],
        num: match[2] ? Number(match[2]) : 0,
        raw,
      };
    }
    return { prefix: raw, num: 0, raw };
  };

  const sortWings = (a, b) => {
    const wa = parseWingName(a.wing_name);
    const wb = parseWingName(b.wing_name);
    const prefixCmp = wa.prefix.localeCompare(wb.prefix, undefined, { sensitivity: 'base' });
    if (prefixCmp !== 0) return prefixCmp;
    if (wa.num !== wb.num) return wa.num - wb.num;
    return wa.raw.localeCompare(wb.raw, undefined, { sensitivity: 'base', numeric: true });
  };

  const fetchMapping = async () => {
    try {
      const res = await adminAPI.getFlatMapping();
      setMapping(res.data);
    } catch (e) {
      toast.error('Failed to load flat mapping');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMapping();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  return (
    <div data-testid="flat-mapping-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Flat Mapping</h1>
        <p className="text-text-secondary mt-1">View-only flat mapping (only Platform Owner can add/edit/remove)</p>
      </div>

      {mapping.length === 0 ? (
        <div className="card p-12 text-center">
          <Home className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No Wings Yet</h3>
          <p className="text-text-secondary">Create wings first to add flats</p>
        </div>
      ) : (
        <div className="space-y-8">
          {[...mapping].sort(sortWings).map((wing) => (
            <div key={wing.wing_id} className="card p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-semibold text-text-primary">Wing {wing.wing_name}</h2>
                  <p className="text-text-secondary text-sm">
                    {wing.active_flats}/{wing.total_flats} active flats
                  </p>
                </div>
              </div>

              {Object.keys(wing.floors).length === 0 ? (
                <p className="text-text-muted text-center py-8">No flats in this wing</p>
              ) : (
                <div className="space-y-4">
                  {Object.entries(wing.floors)
                    .sort(([a], [b]) => Number(b) - Number(a))
                    .map(([floor, flats]) => (
                      <div key={floor} className="flex items-center gap-4">
                        <span className="text-text-secondary text-sm w-20">Floor {floor}</span>
                        <div className="flex flex-wrap gap-2">
                          {flats.map((flat) => (
                            <div
                              key={flat.id}
                              data-testid={`flat-${flat.id}`}
                              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                                flat.is_active
                                  ? 'bg-success/20 text-success border border-success/50'
                                  : 'bg-bg-elevated text-text-muted border border-border-color'
                              }`}
                            >
                              {flat.number}
                              {flat.resident_name && (
                                <span className="block text-xs opacity-75">{flat.resident_name}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const ResidentsManager = () => {
  const [residents, setResidents] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [wings, setWings] = useState([]);
  const [rejectResidentId, setRejectResidentId] = useState(null);

  const fetchData = async () => {
    try {
      const [residentsRes, wingsRes] = await Promise.all([
        adminAPI.getResidents(filter === 'all' ? undefined : filter),
        adminAPI.getWings(),
      ]);
      setResidents(residentsRes.data);
      setWings(wingsRes.data);
    } catch (e) {
      toast.error('Failed to load residents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [filter]);

  const handleApprove = async (residentId) => {
    try {
      await adminAPI.approveResident(residentId);
      toast.success('Resident approved');
      fetchData();
    } catch (e) {
      toast.error('Failed to approve resident');
    }
  };

  const handleReject = async () => {
    try {
      await adminAPI.rejectResident(rejectResidentId);
      toast.success('Resident rejected');
      fetchData();
    } catch (e) {
      toast.error('Failed to reject resident');
    } finally {
      setRejectResidentId(null);
    }
  };

  const handlePromote = async (residentId, wingId) => {
    try {
      await adminAPI.promoteToSubAdmin(residentId, wingId);
      toast.success('Resident promoted to Sub-Admin');
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to promote resident');
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
    <div data-testid="residents-manager-page" className="space-y-6">
      <div className="page-header">
        <div>
          <h1 className="text-[28px] font-bold text-text-primary">Residents</h1>
          <p className="text-text-secondary mt-1">Manage society residents</p>
        </div>
        <div className="tabs-scroll">
          {['all', 'pending', 'active'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              data-testid={`filter-${f}`}
              className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === f
                  ? 'bg-accent text-white'
                  : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="table-mobile-wrapper">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="text-left p-3 sm:p-4">Resident</th>
                <th className="text-left p-3 sm:p-4">Flat</th>
                <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Wing</th>
                <th className="text-left p-3 sm:p-4">Status</th>
                <th className="text-left p-3 sm:p-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {residents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-text-secondary">
                    <Users className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No residents found</p>
                  </td>
                </tr>
              ) : (
                residents.map((resident) => (
                  <tr key={resident.id} className="table-row">
                    <td className="p-3 sm:p-4">
                      <div>
                        <p className="font-medium text-text-primary text-sm">{resident.name}</p>
                        <p className="text-xs text-text-secondary">{resident.mobile}</p>
                      </div>
                    </td>
                    <td className="p-3 sm:p-4 text-text-primary text-sm">
                      {resident.flat?.number || 'Not assigned'}
                    </td>
                    <td className="p-3 sm:p-4 text-text-primary hidden sm:table-cell">
                      {resident.wing?.name || '-'}
                    </td>
                    <td className="p-3 sm:p-4">{getStatusBadge(resident.status)}</td>
                    <td className="p-3 sm:p-4">
                      <div className="flex gap-2 flex-wrap">
                        {resident.status === 'pending' && (
                          <>
                            <button
                              onClick={() => handleApprove(resident.id)}
                              data-testid={`approve-resident-${resident.id}`}
                              className="p-1.5 sm:p-2 bg-success/20 text-success rounded-lg hover:bg-success/30 transition-colors"
                            >
                              <CheckCircle className="w-4 h-4 sm:w-5 sm:h-5" />
                            </button>
                            <button
                              onClick={() => setRejectResidentId(resident.id)}
                              data-testid={`reject-resident-${resident.id}`}
                              className="p-1.5 sm:p-2 bg-danger/20 text-danger rounded-lg hover:bg-danger/30 transition-colors"
                            >
                              <XCircle className="w-4 h-4 sm:w-5 sm:h-5" />
                            </button>
                          </>
                        )}
                        {resident.status === 'active' && wings.length > 0 && (
                          <select
                            onChange={(e) => {
                              if (e.target.value) {
                                handlePromote(resident.id, e.target.value);
                              }
                            }}
                            data-testid={`promote-resident-${resident.id}`}
                            className="input-field text-xs sm:text-sm py-1"
                            defaultValue=""
                          >
                            <option value="">Promote</option>
                            {wings.filter(w => !w.sub_admin_id).map((wing) => (
                              <option key={wing.id} value={wing.id}>
                                Wing {wing.name}
                              </option>
                            ))}
                          </select>
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

      <ConfirmDialog
        open={!!rejectResidentId}
        onOpenChange={(open) => !open && setRejectResidentId(null)}
        title="Reject Resident?"
        description="Are you sure you want to reject this resident's registration request?"
        confirmLabel="Yes, Reject"
        onConfirm={handleReject}
        testIdPrefix="reject-resident"
      />
    </div>
  );
};

export { AdminDashboard, WingsManager, FlatMapping, ResidentsManager };
