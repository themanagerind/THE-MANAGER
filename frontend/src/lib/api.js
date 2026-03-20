import axios from 'axios';
import useAuthStore from '../store/authStore';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth APIs
export const authAPI = {
  login: (mobile, password, role) => api.post('/auth/login', { mobile, password, role }),
  register: (data) => api.post('/auth/register', data),
  registerAdmin: (data, societyName, societyAddress) => 
    api.post(`/auth/register-admin?society_name=${encodeURIComponent(societyName)}&society_address=${encodeURIComponent(societyAddress)}`, data),
  getMe: () => api.get('/auth/me'),
  getRoles: () => api.get('/auth/roles'),
  switchRole: (targetRole) => api.post('/auth/switch-role', { target_role: targetRole }),
};

// Platform Owner APIs
export const platformAPI = {
  getAdmins: () => api.get('/platform/admins'),
  approveAdmin: (adminId) => api.post(`/platform/admins/${adminId}/approve`),
  blockAdmin: (adminId) => api.post(`/platform/admins/${adminId}/block`),
  unblockAdmin: (adminId) => api.post(`/platform/admins/${adminId}/unblock`),
  getShoppingLink: () => api.get('/platform/shopping-link'),
  setShoppingLink: (link) => api.put('/platform/shopping-link', { shopping_link: link }),
  getStats: () => api.get('/platform/stats'),
};

// Admin APIs
export const adminAPI = {
  // Wings
  createWing: (data) => api.post('/admin/wings', data),
  getWings: () => api.get('/admin/wings'),
  updateWing: (wingId, name) => api.put(`/admin/wings/${wingId}?name=${encodeURIComponent(name)}`),
  deleteWing: (wingId) => api.delete(`/admin/wings/${wingId}`),
  assignSubAdmin: (wingId, subAdminId) => api.put(`/admin/wings/${wingId}/assign-subadmin?sub_admin_id=${subAdminId}`),
  
  // Flats
  createFlat: (data) => api.post('/admin/flats', data),
  createFlatsBulk: (wingId, floorCount, flatsPerFloor) => 
    api.post(`/admin/flats/bulk?wing_id=${wingId}&floor_count=${floorCount}&flats_per_floor=${flatsPerFloor}`),
  getFlats: (wingId) => api.get('/admin/flats', { params: { wing_id: wingId } }),
  getFlatMapping: () => api.get('/admin/flats/mapping'),
  toggleFlat: (flatId, isActive) => api.put(`/admin/flats/${flatId}/toggle`, { is_active: isActive }),
  assignResident: (flatId, residentId) => api.put(`/admin/flats/${flatId}/assign-resident?resident_id=${residentId}`),
  
  // Residents
  getResidents: (status) => api.get('/admin/residents', { params: { status } }),
  approveResident: (residentId) => api.post(`/admin/residents/${residentId}/approve`),
  rejectResident: (residentId) => api.post(`/admin/residents/${residentId}/reject`),
  promoteToSubAdmin: (residentId, wingId) => api.post(`/admin/residents/${residentId}/promote?wing_id=${wingId}`),
  getSubAdmins: () => api.get('/admin/sub-admins'),
  
  // Income
  createIncome: (data) => api.post('/admin/income', data),
  getIncome: () => api.get('/admin/income'),
  
  // Expenses
  createExpense: (data) => api.post('/admin/expenses', data),
  getExpenses: () => api.get('/admin/expenses'),
  
  // Plans
  createPlan: (data) => api.post('/admin/plans', data),
  getPlans: () => api.get('/admin/plans'),
};

// Maintenance APIs
export const maintenanceAPI = {
  // Admin
  preview: (month, amountPerFlat) => api.get('/maintenance/admin/preview', { params: { month, amount_per_flat: amountPerFlat } }),
  generate: (data) => api.post('/maintenance/admin/generate', data),
  getBills: (params) => api.get('/maintenance/admin/bills', { params }),
  cancelBill: (billId, reason) => api.put(`/maintenance/admin/bills/${billId}/cancel`, { reason }),
  restoreBill: (billId) => api.put(`/maintenance/admin/bills/${billId}/restore`),
  getAudit: (month) => api.get('/maintenance/admin/audit', { params: { month } }),
  getBatches: () => api.get('/maintenance/admin/batches'),
  
  // Sub-Admin
  getPendingPayments: () => api.get('/maintenance/subadmin/pending'),
  verifyPayment: (billId, action, reason) => api.post(`/maintenance/subadmin/verify/${billId}`, { action, reason }),
  
  // Resident
  getMyBills: () => api.get('/maintenance/resident/bills'),
  payBill: (billId, paymentMode, paymentRef) => api.post(`/maintenance/resident/bills/${billId}/pay`, { payment_mode: paymentMode, payment_ref: paymentRef }),
  
  // Wallet
  getWallet: () => api.get('/maintenance/wallet'),
};

// Sub-Admin APIs
export const subAdminAPI = {
  getPendingExpenses: () => api.get('/subadmin/expenses/pending'),
  verifyExpense: (expenseId, decision, reason) => api.post(`/subadmin/expenses/${expenseId}/verify`, { decision, reason }),
  getPendingPlans: () => api.get('/subadmin/plans/pending'),
  approvePlan: (planId, decision, reason) => api.post(`/subadmin/plans/${planId}/approve`, { decision, reason }),
};

// Reports APIs
export const reportsAPI = {
  getIncome: () => api.get('/reports/income'),
  getExpenses: () => api.get('/reports/expenses'),
  getOutstandingSummary: () => api.get('/reports/outstanding'),
  getOutstandingDetail: (month) => api.get(`/reports/outstanding/${month}`),
};

// Notices & Complaints APIs
export const miscAPI = {
  // Notices
  createNotice: (data) => api.post('/notices', data),
  getNotices: () => api.get('/notices'),
  updateNotice: (noticeId, data) => api.put(`/notices/${noticeId}`, data),
  deleteNotice: (noticeId) => api.delete(`/notices/${noticeId}`),
  
  // Complaints
  createComplaint: (data) => api.post('/complaints', data),
  getComplaints: (status) => api.get('/complaints', { params: { status } }),
  updateComplaintStatus: (complaintId, data) => api.put(`/complaints/${complaintId}/status`, data),
  
  // Bazaar
  getBazaarLink: () => api.get('/bazaar/link'),
};

export default api;
