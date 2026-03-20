import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, IndianRupee, AlertTriangle } from 'lucide-react';
import { reportsAPI } from '../../lib/api';
import { toast } from 'sonner';
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
  const [activeTab, setActiveTab] = useState('income');
  const [incomeData, setIncomeData] = useState({ entries: [], total: 0 });
  const [expenseData, setExpenseData] = useState({ entries: [], total: 0 });
  const [outstandingSummary, setOutstandingSummary] = useState([]);
  const [outstandingDetail, setOutstandingDetail] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [incomeRes, expenseRes, outstandingRes] = await Promise.all([
          reportsAPI.getIncome(),
          reportsAPI.getExpenses(),
          reportsAPI.getOutstandingSummary(),
        ]);
        setIncomeData(incomeRes.data);
        setExpenseData(expenseRes.data);
        setOutstandingSummary(outstandingRes.data);
      } catch (e) {
        toast.error('Failed to load reports');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const fetchOutstandingDetail = async (month) => {
    try {
      const res = await reportsAPI.getOutstandingDetail(month);
      setOutstandingDetail(res.data);
      setSelectedMonth(month);
    } catch (e) {
      toast.error('Failed to load details');
    }
  };

  const tabs = [
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
      <div className="flex gap-2 border-b border-border-color pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`tab-${tab.id}`}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === tab.id
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Income Report */}
      {activeTab === 'income' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="text-left p-4">Date</th>
                    <th className="text-left p-4">Title</th>
                    <th className="text-left p-4">Category</th>
                    <th className="text-right p-4">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {incomeData.entries.map((entry, i) => (
                    <tr key={i} className="table-row">
                      <td className="p-4 text-text-primary">{entry.entry_date}</td>
                      <td className="p-4 text-text-primary">{entry.title}</td>
                      <td className="p-4">
                        <span className="badge-info">{entry.category}</span>
                      </td>
                      <td className="p-4 text-right text-success font-medium">
                        ₹{entry.amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-success/10">
                  <tr>
                    <td colSpan={3} className="p-4 font-bold text-text-primary">Grand Total</td>
                    <td className="p-4 text-right font-bold text-success text-lg">
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
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="table-header">
                  <tr>
                    <th className="text-left p-4">Date</th>
                    <th className="text-left p-4">Title</th>
                    <th className="text-left p-4">Category</th>
                    <th className="text-left p-4">Status</th>
                    <th className="text-right p-4">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {expenseData.entries.map((entry, i) => (
                    <tr key={i} className="table-row">
                      <td className="p-4 text-text-primary">{entry.bill_date}</td>
                      <td className="p-4 text-text-primary">{entry.title}</td>
                      <td className="p-4">
                        <span className="badge-info">{entry.category}</span>
                      </td>
                      <td className="p-4">
                        {entry.status === 'verified' ? (
                          <span className="badge-success">Verified</span>
                        ) : entry.status === 'rejected' ? (
                          <span className="badge-danger">Rejected</span>
                        ) : (
                          <span className="badge-warning">Pending</span>
                        )}
                      </td>
                      <td className="p-4 text-right text-danger font-medium">
                        ₹{entry.amount.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-danger/10">
                  <tr>
                    <td colSpan={4} className="p-4 font-bold text-text-primary">Grand Total</td>
                    <td className="p-4 text-right font-bold text-danger text-lg">
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
              <div className="p-4 border-b border-border-color bg-danger/10">
                <h3 className="font-semibold text-danger">
                  Outstanding Details for {outstandingDetail.month}
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-danger/10">
                    <tr>
                      <th className="text-left p-4 text-danger">Flat</th>
                      <th className="text-left p-4 text-danger">Wing</th>
                      <th className="text-left p-4 text-danger">Resident</th>
                      <th className="text-left p-4 text-danger">Months Pending</th>
                      <th className="text-right p-4 text-danger">Outstanding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outstandingDetail.flats.map((flat, i) => (
                      <tr key={i} className="table-row">
                        <td className="p-4 font-medium text-danger">{flat.flat_number}</td>
                        <td className="p-4 text-danger">{flat.wing_name}</td>
                        <td className="p-4 text-danger">{flat.resident_name}</td>
                        <td className="p-4 text-danger">{flat.months_pending?.length || 0}</td>
                        <td className="p-4 text-right font-bold text-danger">
                          ₹{flat.total_outstanding.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-danger/20">
                    <tr>
                      <td colSpan={4} className="p-4 font-bold text-danger text-lg">
                        Grand Total
                      </td>
                      <td className="p-4 text-right font-bold text-danger text-xl">
                        ₹{outstandingDetail.grand_total.toLocaleString()}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
