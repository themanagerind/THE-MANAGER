import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, IndianRupee, AlertTriangle, Receipt, CheckCircle } from 'lucide-react';
import { reportsAPI, maintenanceAPI } from '../../lib/api';
import { toast } from 'sonner';
import useAuthStore from '../../store/authStore';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#E67E22', '#27AE60', '#2E86C1', '#F39C12', '#9B59B6'];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-bg-surface border border-border-color rounded-lg p-3 shadow-lg">
        <p className="text-text-primary font-medium">{label}</p>
        {payload.map((item, index) => (
          <p key={index} className="text-text-secondary text-sm">
            {item.name}: ₹{item.value?.toLocaleString()}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const ReportsPage = () => {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('income');
  const [incomeData, setIncomeData] = useState({ entries: [], total: 0 });
  const [expenseData, setExpenseData] = useState({ entries: [], total: 0 });
  const [outstandingSummary, setOutstandingSummary] = useState([]);
  const [outstandingDetail, setOutstandingDetail] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [residentBills, setResidentBills] = useState([]);
  const [wallet, setWallet] = useState({ balance: 0 });
  const [loading, setLoading] = useState(true);

  const isResident = user?.role === 'resident';

  useEffect(() => {
    const fetchData = async () => {
      try {
        if (isResident) {
          // Fetch resident's bills
          const billsRes = await maintenanceAPI.getMyBills();
          setResidentBills(billsRes.data);
        } else {
          // Fetch admin reports
          const [incomeRes, expenseRes, outstandingRes, walletRes] = await Promise.all([
            reportsAPI.getIncome(),
            reportsAPI.getExpenses(),
            reportsAPI.getOutstandingSummary(),
            maintenanceAPI.getWallet().catch(() => ({ data: { balance: 0 } })),
          ]);

          // Also fetch maintenance batches and bills to include maintenance as income
          let maintenanceEntries = [];
          try {
            const batchesRes = await maintenanceAPI.getBatches();
            // limit to recent 12 batches to avoid excessive requests
            const batches = (batchesRes.data || []).slice(0, 12);
            const billsByBatch = await Promise.all(
              batches.map((b) => maintenanceAPI.getBills({ month: b.month }).then(r => ({ month: b.month, bills: r.data })).catch(() => ({ month: b.month, bills: [] })))
            );

            billsByBatch.forEach(({ month, bills }) => {
              const active = (bills || []).filter(b => !b.is_cancelled);
              const collected = active.filter(b => b.status === 'verified' || b.status === 'paid').reduce((s, b) => s + (b.amount || 0), 0);
              if (collected > 0) {
                maintenanceEntries.push({
                  entry_date: month,
                  title: `Maintenance (${month})`,
                  category: 'maintenance',
                  amount: collected,
                });
              }
            });
          } catch (e) {
            // ignore maintenance fetch errors
          }

          const mergedIncomeEntries = [ ...(incomeRes.data.entries || []), ...maintenanceEntries ];
          const maintenanceTotal = maintenanceEntries.reduce((s, e) => s + (e.amount || 0), 0);
          setIncomeData({ entries: mergedIncomeEntries, total: (incomeRes.data.total || 0) + maintenanceTotal });
          setWallet(walletRes.data || { balance: 0 });
          setExpenseData(expenseRes.data);
          setOutstandingSummary(outstandingRes.data);
        }
      } catch (e) {
        toast.error('Failed to load reports');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [isResident]);

  const fetchOutstandingDetail = async (month) => {
    try {
      const res = await reportsAPI.getOutstandingDetail(month);
      setOutstandingDetail(res.data);
      setSelectedMonth(month);
    } catch (e) {
      toast.error('Failed to load details');
    }
  };

  const tabs = isResident 
    ? [{ id: 'outstanding', label: 'Outstanding Dues', icon: AlertTriangle }]
    : [
        { id: 'income', label: 'Income Report', icon: TrendingUp },
        { id: 'expenses', label: 'Expense Report', icon: TrendingDown },
        { id: 'outstanding', label: 'Outstanding Report', icon: AlertTriangle },
      ];

  if (loading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-bg-surface rounded w-48" />
        <div className="h-96 bg-bg-surface rounded-xl" />
      </div>
    );
  }

  // Prepare chart data
  const incomeByCategory = incomeData.entries.reduce((acc, entry) => {
    const existing = acc.find(a => a.name === entry.category);
    if (existing) {
      existing.value += entry.amount;
    } else {
      acc.push({ name: entry.category, value: entry.amount });
    }
    return acc;
  }, []);

  return (
    <div data-testid="reports-page" className="space-y-6">
      <div>
        <h1 className="text-[28px] font-bold text-text-primary">Reports</h1>
        <p className="text-text-secondary mt-1">Financial overview and analysis</p>
      </div>

      {/* Tabs */}
      <div className="tabs-scroll border-b border-border-color pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg transition-colors text-sm sm:text-base ${
              activeTab === tab.id
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            <span className="hidden sm:inline">{tab.label}</span>
            <span className="sm:hidden">{tab.id === 'income' ? 'Income' : tab.id === 'expenses' ? 'Expenses' : 'Outstanding'}</span>
          </button>
        ))}
      </div>

      {/* Income Report */}
      {activeTab === 'income' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-success/20 rounded-lg">
                  <TrendingUp className="w-6 h-6 text-success" />
                </div>
                <div>
                  <p className="text-text-secondary text-sm">Total Income</p>
                  <p className="text-2xl font-bold text-success">₹{incomeData.total.toLocaleString()}</p>
                </div>
              </div>
            </div>
            <div className="card p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-3 bg-accent-light rounded-lg">
                  <IndianRupee className="w-6 h-6 text-accent" />
                </div>
                <div>
                  <p className="text-text-secondary text-sm">Credit Balance</p>
                  <p className="text-2xl font-bold text-accent">{wallet.balance}</p>
                </div>
              </div>
            </div>
            
            <div className="lg:col-span-2 card p-6">
              <h3 className="font-semibold text-text-primary mb-4">Income by Category</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={incomeByCategory}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                    >
                      {incomeByCategory.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="table-mobile-wrapper">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="text-left p-3 sm:p-4">Date</th>
                    <th className="text-left p-3 sm:p-4">Title</th>
                    <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Category</th>
                    <th className="text-right p-3 sm:p-4">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {incomeData.entries.map((entry, i) => (
                    <tr key={i} className="table-row">
                      <td className="p-3 sm:p-4 text-text-primary text-sm">{entry.entry_date}</td>
                      <td className="p-3 sm:p-4 text-text-primary text-sm">{entry.title}</td>
                      <td className="p-3 sm:p-4 hidden sm:table-cell">
                        <span className="badge-info">{entry.category}</span>
                      </td>
                      <td className="p-3 sm:p-4 text-right text-success font-medium">
                        ₹{entry.amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-success/10">
                  <tr>
                    <td colSpan={2} className="p-3 sm:p-4 font-bold text-text-primary">Grand Total</td>
                    <td className="p-3 sm:p-4 hidden sm:table-cell"></td>
                    <td className="p-3 sm:p-4 text-right font-bold text-success text-lg">
                      ₹{incomeData.total.toLocaleString()}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Expense Report */}
      {activeTab === 'expenses' && (
        <div className="space-y-6">
          <div className="card p-6">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-danger/20 rounded-lg">
                <TrendingDown className="w-6 h-6 text-danger" />
              </div>
              <div>
                <p className="text-text-secondary text-sm">Total Expenses</p>
                <p className="text-2xl font-bold text-danger">₹{expenseData.total.toLocaleString()}</p>
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="table-mobile-wrapper">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="text-left p-3 sm:p-4">Title</th>
                    <th className="text-left p-3 sm:p-4 hidden sm:table-cell">Category</th>
                    <th className="text-left p-3 sm:p-4">Status</th>
                    <th className="text-right p-3 sm:p-4">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {expenseData.entries.map((entry, i) => (
                    <tr key={i} className="table-row">
                      <td className="p-3 sm:p-4 text-text-primary text-sm">{entry.title}</td>
                      <td className="p-3 sm:p-4 hidden sm:table-cell">
                        <span className="badge-info">{entry.category}</span>
                      </td>
                      <td className="p-3 sm:p-4">
                        {entry.status === 'verified' ? (
                          <span className="badge-success">Verified</span>
                        ) : entry.status === 'rejected' ? (
                          <span className="badge-danger">Rejected</span>
                        ) : (
                          <span className="badge-warning">Pending</span>
                        )}
                      </td>
                      <td className="p-3 sm:p-4 text-right text-danger font-medium">
                        ₹{entry.amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-danger/10">
                  <tr>
                    <td className="p-3 sm:p-4 font-bold text-text-primary">Grand Total</td>
                    <td className="p-3 sm:p-4 hidden sm:table-cell"></td>
                    <td className="p-3 sm:p-4"></td>
                    <td className="p-3 sm:p-4 text-right font-bold text-danger text-lg">
                      ₹{expenseData.total.toLocaleString()}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Outstanding Report */}
      {activeTab === 'outstanding' && (
        <div className="space-y-6">
          {/* Month Summary */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-4">
            {outstandingSummary.map((item) => (
              <button
                key={item.month}
                onClick={() => fetchOutstandingDetail(item.month)}
                data-testid={`outstanding-${item.month}`}
                className={`card p-4 text-left transition-all hover:ring-2 hover:ring-danger ${
                  selectedMonth === item.month ? 'ring-2 ring-danger' : ''
                }`}
              >
                <p className="text-text-secondary text-sm">{item.month}</p>
                <p className="text-2xl font-bold text-danger">
                  ₹{item.total_outstanding.toLocaleString()}
                </p>
                <p className="text-sm text-danger">{item.unpaid_count} unpaid</p>
              </button>
            ))}
          </div>

          {/* Outstanding Detail - ALL TEXT IN RED */}
          {outstandingDetail && (
            <div className="card overflow-hidden">
              <div className="p-3 sm:p-4 border-b border-border-color bg-danger/10">
                <h3 className="font-semibold text-danger text-sm sm:text-base">
                  Outstanding Details for {outstandingDetail.month}
                </h3>
              </div>
              <div className="table-mobile-wrapper">
                <table className="w-full">
                  <thead className="bg-danger/10">
                    <tr>
                      <th className="text-left p-3 sm:p-4 text-danger">Flat</th>
                      <th className="text-left p-3 sm:p-4 text-danger hidden sm:table-cell">Wing</th>
                      <th className="text-left p-3 sm:p-4 text-danger">Resident</th>
                      <th className="text-left p-3 sm:p-4 text-danger hidden sm:table-cell">Pending</th>
                      <th className="text-right p-3 sm:p-4 text-danger">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outstandingDetail.flats.map((flat, i) => (
                      <tr key={i} className="table-row">
                        <td className="p-3 sm:p-4 font-medium text-danger text-sm">{flat.flat_number}</td>
                        <td className="p-3 sm:p-4 text-danger hidden sm:table-cell">{flat.wing_name}</td>
                        <td className="p-3 sm:p-4 text-danger text-sm">{flat.resident_name}</td>
                        <td className="p-3 sm:p-4 text-danger hidden sm:table-cell">{flat.months_pending?.length || 0}</td>
                        <td className="p-3 sm:p-4 text-right font-bold text-danger">
                          ₹{flat.total_outstanding.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-danger/20">
                    <tr>
                      <td colSpan={2} className="p-3 sm:p-4 font-bold text-danger sm:text-lg">
                        Grand Total
                      </td>
                      <td className="p-3 sm:p-4 hidden sm:table-cell"></td>
                      <td className="p-3 sm:p-4 hidden sm:table-cell"></td>
                      <td className="p-3 sm:p-4 text-right font-bold text-danger text-lg sm:text-xl">
                        ₹{outstandingDetail.grand_total.toLocaleString()}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
              {/* Additional details: Expenses and Other Income for the selected month */}
              <div className="p-4 sm:p-6 border-t border-border-color">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-semibold mb-2">Expenses for {selectedMonth}</h4>
                    <div className="overflow-auto max-h-48">
                      <table className="w-full">
                        <thead>
                          <tr>
                            <th className="text-left p-2 text-sm">Title</th>
                            <th className="text-right p-2 text-sm">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {expenseData.entries
                            .filter((e) => {
                              const d = (e.entry_date || e.date || '').toString();
                              return selectedMonth ? d.startsWith(selectedMonth) : true;
                            })
                            .map((e, i) => (
                              <tr key={i}>
                                <td className="p-2 text-sm">{e.title}</td>
                                <td className="p-2 text-right text-danger">₹{(e.amount || 0).toLocaleString()}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Income (including Maintenance) for {selectedMonth}</h4>
                    <div className="overflow-auto max-h-48">
                      <table className="w-full">
                        <thead>
                          <tr>
                            <th className="text-left p-2 text-sm">Title</th>
                            <th className="text-right p-2 text-sm">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {incomeData.entries
                            .filter((e) => {
                              const d = (e.entry_date || e.date || '').toString();
                              return selectedMonth ? d.startsWith(selectedMonth) : true;
                            })
                            .map((e, i) => (
                              <tr key={i}>
                                <td className="p-2 text-sm">{e.title}</td>
                                <td className="p-2 text-right text-success">₹{(e.amount || 0).toLocaleString()}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
