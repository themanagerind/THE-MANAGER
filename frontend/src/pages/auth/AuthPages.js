import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Building2, Eye, EyeOff, Phone, Lock, User, ChevronRight, ArrowLeft, Shield, KeyRound } from 'lucide-react';
import { authAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';

const Login = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({ mobile: '', password: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await authAPI.login(formData.mobile, formData.password);
      const { access_token, user } = response.data;
      setAuth(user, access_token);
      toast.success(`Welcome back, ${user.name}!`);
      switch (user.role) {
        case 'platform_owner': navigate('/platform'); break;
        case 'admin': navigate('/admin'); break;
        case 'sub_admin': navigate('/subadmin'); break;
        case 'resident': navigate('/resident'); break;
        default: navigate('/');
      }
    } catch (error) {
      const detail = error.response?.data?.detail || 'Login failed';
      if (error.response?.status === 403 && detail.includes('approved')) {
        toast.info(detail);
        navigate('/set-password', { state: { mobile: formData.mobile } });
      } else {
        toast.error(detail);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex">
      <div className="hidden lg:flex lg:w-1/2 relative">
        <img
          src="https://images.unsplash.com/photo-1638369321342-fe20d9bd358f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjY2NzF8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBsdXh1cnklMjBhcGFydG1lbnQlMjBidWlsZGluZyUyMG5pZ2h0JTIwZXh0ZXJpb3J8ZW58MHx8fHwxNzc0MDE2MzU1fDA&ixlib=rb-4.1.0&q=85"
          alt="Modern Apartment Building"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-bg-base via-bg-base/80 to-transparent" />
        <div className="relative z-10 flex flex-col justify-center p-12">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 bg-accent/20 rounded-xl">
              <Building2 className="w-8 h-8 text-accent" />
            </div>
            <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
          </div>
          <h1 className="text-4xl font-bold text-text-primary mb-4">
            Housing Society<br />Management System
          </h1>
          <p className="text-text-secondary text-lg max-w-md">
            Manage your society efficiently with our comprehensive platform for bills, payments, and community engagement.
          </p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="p-3 bg-accent/20 rounded-xl">
              <Building2 className="w-8 h-8 text-accent" />
            </div>
            <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
          </div>

          <div className="card p-8">
            <h2 className="text-2xl font-bold text-text-primary mb-2">Welcome Back</h2>
            <p className="text-text-secondary mb-8">Sign in to your account</p>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input
                    type="text"
                    data-testid="login-mobile-input"
                    value={formData.mobile}
                    onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
                    className="input-field w-full pl-10"
                    placeholder="Enter mobile number"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    data-testid="login-password-input"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="input-field w-full pl-10 pr-10"
                    placeholder="Enter password"
                    required
                  />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              <button type="submit" data-testid="login-submit-btn" disabled={loading}
                className="btn-primary w-full py-3 disabled:opacity-50">
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <div className="mt-4 text-center">
              <Link to="/forgot-password" className="text-accent hover:underline text-sm" data-testid="forgot-password-link">
                Forgot Password?
              </Link>
            </div>

            <div className="mt-6 text-center">
              <p className="text-text-secondary">
                New Resident?{' '}
                <Link to="/register" className="text-accent hover:underline" data-testid="register-link">Register here</Link>
              </p>
              <p className="text-text-secondary mt-2">
                <Link to="/register-admin" className="text-text-muted hover:text-accent text-sm" data-testid="register-admin-link">
                  Register as Society Admin
                </Link>
              </p>
            </div>

            <div className="mt-4 pt-4 border-t border-border-color">
              <p className="text-text-muted text-sm text-center mb-2">Demo Credentials</p>
              <div className="text-xs text-text-secondary space-y-1">
                <p>Platform Owner: 9999999999 / owner123</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Register = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1=form, 2=otp, 3=success
  const [loading, setLoading] = useState(false);
  const [societies, setSocieties] = useState([]);
  const [wings, setWings] = useState([]);
  const [flats, setFlats] = useState([]);
  const [otpTimer, setOtpTimer] = useState(0);
  const [otpToken, setOtpToken] = useState('');
  const [mockOtp, setMockOtp] = useState('');
  const [formData, setFormData] = useState({
    name: '', mobile: '', society_id: '', wing_id: '', flat_id: '', otp: ''
  });

  useEffect(() => {
    const fetchSocieties = async () => {
      try {
        const res = await authAPI.getSocieties();
        setSocieties(res.data);
      } catch (e) { /* no societies yet */ }
    };
    fetchSocieties();
  }, []);

  useEffect(() => {
    if (formData.society_id) {
      const fetchWings = async () => {
        try {
          const res = await authAPI.getSocietyWings(formData.society_id);
          setWings(res.data);
          setFormData(f => ({ ...f, wing_id: '', flat_id: '' }));
          setFlats([]);
        } catch (e) { setWings([]); }
      };
      fetchWings();
    }
  }, [formData.society_id]);

  useEffect(() => {
    if (formData.wing_id) {
      const fetchFlats = async () => {
        try {
          const res = await authAPI.getWingFlats(formData.wing_id);
          setFlats(res.data);
          setFormData(f => ({ ...f, flat_id: '' }));
        } catch (e) { setFlats([]); }
      };
      fetchFlats();
    }
  }, [formData.wing_id]);

  useEffect(() => {
    if (otpTimer > 0) {
      const t = setTimeout(() => setOtpTimer(otpTimer - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [otpTimer]);

  const handleSendOTP = async () => {
    if (!formData.name || !formData.mobile || !formData.society_id || !formData.wing_id || !formData.flat_id) {
      toast.error('Please fill all fields');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.sendOTP(formData.mobile, 'signup');
      setMockOtp(res.data.mock_otp || '');
      setOtpTimer(Math.floor(res.data.expires_in));
      setStep(2);
      toast.success('OTP sent to your mobile');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (formData.otp.length !== 6) {
      toast.error('Enter 6-digit OTP');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.verifyOTP(formData.mobile, formData.otp, 'signup');
      setOtpToken(res.data.otp_token);
      // Now register
      await authAPI.register({
        name: formData.name,
        mobile: formData.mobile,
        otp_token: res.data.otp_token,
        society_id: formData.society_id,
        wing_id: formData.wing_id,
        flat_id: formData.flat_id,
      });
      setStep(3);
      toast.success('Registration submitted! Waiting for admin approval.');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOTP = async () => {
    try {
      const res = await authAPI.sendOTP(formData.mobile, 'signup');
      setMockOtp(res.data.mock_otp || '');
      setOtpTimer(Math.floor(res.data.expires_in));
      setFormData(f => ({ ...f, otp: '' }));
      toast.success('OTP resent');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to resend OTP');
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="p-3 bg-accent/20 rounded-xl">
            <Building2 className="w-8 h-8 text-accent" />
          </div>
          <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
        </div>

        <div className="card p-8">
          {step === 1 && (
            <>
              <h2 className="text-2xl font-bold text-text-primary mb-2">Resident Registration</h2>
              <p className="text-text-secondary mb-6">Join your housing society</p>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Full Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input type="text" data-testid="register-name-input" value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="input-field w-full pl-10" placeholder="Enter your name" required />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input type="text" data-testid="register-mobile-input" value={formData.mobile}
                      onChange={(e) => setFormData({ ...formData, mobile: e.target.value.replace(/\D/g, '').slice(0, 10) })}
                      className="input-field w-full pl-10" placeholder="10-digit mobile number" maxLength={10} required />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Society</label>
                  <select data-testid="register-society-select" value={formData.society_id}
                    onChange={(e) => setFormData({ ...formData, society_id: e.target.value })}
                    className="input-field w-full" required>
                    <option value="">Select Society</option>
                    {societies.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  {societies.length === 0 && (
                    <p className="text-text-muted text-xs mt-1">No societies available yet</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Wing</label>
                  <select data-testid="register-wing-select" value={formData.wing_id}
                    onChange={(e) => setFormData({ ...formData, wing_id: e.target.value })}
                    className="input-field w-full" disabled={!formData.society_id} required>
                    <option value="">Select Wing</option>
                    {wings.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Flat Number</label>
                  <select data-testid="register-flat-select" value={formData.flat_id}
                    onChange={(e) => setFormData({ ...formData, flat_id: e.target.value })}
                    className="input-field w-full" disabled={!formData.wing_id} required>
                    <option value="">Select Flat</option>
                    {flats.map(f => <option key={f.id} value={f.id}>{f.number}</option>)}
                  </select>
                </div>

                <button onClick={handleSendOTP} data-testid="send-otp-btn" disabled={loading}
                  className="btn-primary w-full py-3 disabled:opacity-50 flex items-center justify-center gap-2">
                  {loading ? 'Sending OTP...' : <>Send OTP <ChevronRight className="w-4 h-4" /></>}
                </button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <button onClick={() => setStep(1)} className="flex items-center gap-1 text-text-secondary hover:text-text-primary mb-4 text-sm">
                <ArrowLeft className="w-4 h-4" /> Back
              </button>
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-accent/20 rounded-xl">
                  <Shield className="w-6 h-6 text-accent" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-text-primary">Verify OTP</h2>
                  <p className="text-text-secondary text-sm">Sent to {formData.mobile}</p>
                </div>
              </div>

              {mockOtp && (
                <div className="mb-4 p-3 bg-accent/10 border border-accent/30 rounded-lg">
                  <p className="text-accent text-sm font-medium">Test Mode - OTP: {mockOtp}</p>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Enter 6-digit OTP</label>
                  <input type="text" data-testid="otp-input" value={formData.otp}
                    onChange={(e) => setFormData({ ...formData, otp: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                    className="input-field w-full text-center text-2xl tracking-[0.5em] font-mono"
                    placeholder="------" maxLength={6} autoFocus />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">
                    {otpTimer > 0 ? `Expires in ${Math.floor(otpTimer / 60)}:${String(otpTimer % 60).padStart(2, '0')}` : 'OTP expired'}
                  </span>
                  <button onClick={handleResendOTP} disabled={otpTimer > 240}
                    className="text-accent hover:underline disabled:opacity-50 disabled:no-underline"
                    data-testid="resend-otp-btn">
                    Resend OTP
                  </button>
                </div>
                <button onClick={handleVerifyOTP} data-testid="verify-otp-btn" disabled={loading || formData.otp.length !== 6}
                  className="btn-primary w-full py-3 disabled:opacity-50">
                  {loading ? 'Verifying...' : 'Verify & Register'}
                </button>
              </div>
            </>
          )}

          {step === 3 && (
            <div className="text-center py-6">
              <div className="w-16 h-16 bg-success/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Shield className="w-8 h-8 text-success" />
              </div>
              <h2 className="text-xl font-bold text-text-primary mb-2">Registration Submitted!</h2>
              <p className="text-text-secondary mb-6">
                Your account is pending admin approval. Once approved, you'll be able to set your password and login.
              </p>
              <Link to="/login" className="btn-primary py-2 px-6" data-testid="goto-login-btn">
                Go to Login
              </Link>
            </div>
          )}

          {step !== 3 && (
            <div className="mt-6 text-center">
              <p className="text-text-secondary">
                Already have an account?{' '}
                <Link to="/login" className="text-accent hover:underline" data-testid="login-link">Sign in</Link>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const RegisterAdmin = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    mobile: '', name: '', email: '', password: '', societyName: '', societyAddress: ''
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authAPI.registerAdmin(
        { mobile: formData.mobile, name: formData.name, email: formData.email, password: formData.password },
        formData.societyName, formData.societyAddress
      );
      toast.success('Admin registration submitted! Waiting for platform owner approval.');
      navigate('/login');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="p-3 bg-accent/20 rounded-xl">
            <Building2 className="w-8 h-8 text-accent" />
          </div>
          <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
        </div>

        <div className="card p-8">
          <h2 className="text-2xl font-bold text-text-primary mb-2">Society Admin Registration</h2>
          <p className="text-text-secondary mb-6">Register your society</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Full Name</label>
              <input type="text" data-testid="admin-reg-name" value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="input-field w-full" placeholder="Enter your name" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
              <input type="text" data-testid="admin-reg-mobile" value={formData.mobile}
                onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
                className="input-field w-full" placeholder="Enter mobile number" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Password</label>
              <div className="relative">
                <input type={showPassword ? 'text' : 'password'} data-testid="admin-reg-password" value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="input-field w-full pr-10" placeholder="Create password" required />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Name</label>
              <input type="text" data-testid="admin-reg-society" value={formData.societyName}
                onChange={(e) => setFormData({ ...formData, societyName: e.target.value })}
                className="input-field w-full" placeholder="Enter society name" required />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">Society Address</label>
              <input type="text" data-testid="admin-reg-address" value={formData.societyAddress}
                onChange={(e) => setFormData({ ...formData, societyAddress: e.target.value })}
                className="input-field w-full" placeholder="Enter society address" required />
            </div>
            <button type="submit" data-testid="admin-reg-submit" disabled={loading}
              className="btn-primary w-full py-3 disabled:opacity-50">
              {loading ? 'Submitting...' : 'Register'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link to="/login" className="text-accent hover:underline text-sm">Back to Login</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

const SetPassword = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mobile, setMobile] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [accountInfo, setAccountInfo] = useState(null);
  const [checked, setChecked] = useState(false);

  const handleCheckStatus = async () => {
    if (!mobile || mobile.length < 10) {
      toast.error('Enter a valid mobile number');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.checkStatus(mobile);
      if (!res.data.exists) {
        toast.error('No account found with this mobile number');
      } else if (res.data.status === 'pending') {
        toast.info('Your account is still pending admin approval');
      } else if (res.data.status === 'approved' && res.data.needs_password_setup) {
        setAccountInfo(res.data);
        setChecked(true);
        toast.success(`Welcome ${res.data.name}! Set your password below.`);
      } else if (res.data.status === 'active') {
        toast.info('Your account is already active. Please login.');
        navigate('/login');
      }
    } catch (e) {
      toast.error('Failed to check status');
    } finally {
      setLoading(false);
    }
  };

  const handleSetPassword = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (password.length < 4) {
      toast.error('Password must be at least 4 characters');
      return;
    }
    setLoading(true);
    try {
      await authAPI.setPassword(mobile, password);
      toast.success('Password set successfully! You can now login.');
      navigate('/login');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to set password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="p-3 bg-accent/20 rounded-xl">
            <KeyRound className="w-8 h-8 text-accent" />
          </div>
          <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
        </div>

        <div className="card p-8">
          <h2 className="text-2xl font-bold text-text-primary mb-2">Set Password</h2>
          <p className="text-text-secondary mb-6">Your account has been approved! Create your login password.</p>

          {!checked ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input type="text" data-testid="set-pwd-mobile" value={mobile}
                    onChange={(e) => setMobile(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    className="input-field w-full pl-10" placeholder="Enter your registered mobile" maxLength={10} />
                </div>
              </div>
              <button onClick={handleCheckStatus} data-testid="check-status-btn" disabled={loading}
                className="btn-primary w-full py-3 disabled:opacity-50">
                {loading ? 'Checking...' : 'Check Account Status'}
              </button>
            </div>
          ) : (
            <form onSubmit={handleSetPassword} className="space-y-4">
              <div className="p-3 bg-bg-elevated rounded-lg mb-2">
                <p className="text-text-secondary text-sm">Setting password for</p>
                <p className="text-text-primary font-medium">{accountInfo?.name} ({mobile})</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input type={showPassword ? 'text' : 'password'} data-testid="set-pwd-password" value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="input-field w-full pl-10 pr-10" placeholder="4-20 characters" required />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input type="password" data-testid="set-pwd-confirm" value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="input-field w-full pl-10" placeholder="Confirm password" required />
                </div>
              </div>
              <button type="submit" data-testid="set-pwd-submit" disabled={loading}
                className="btn-primary w-full py-3 disabled:opacity-50">
                {loading ? 'Setting...' : 'Set Password & Activate'}
              </button>
            </form>
          )}

          <div className="mt-6 text-center">
            <Link to="/login" className="text-accent hover:underline text-sm">Back to Login</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

const ForgotPassword = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1=mobile, 2=otp, 3=new_password
  const [loading, setLoading] = useState(false);
  const [mobile, setMobile] = useState('');
  const [otp, setOtp] = useState('');
  const [otpToken, setOtpToken] = useState('');
  const [mockOtp, setMockOtp] = useState('');
  const [otpTimer, setOtpTimer] = useState(0);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (otpTimer > 0) {
      const t = setTimeout(() => setOtpTimer(otpTimer - 1), 1000);
      return () => clearTimeout(t);
    }
  }, [otpTimer]);

  const handleSendOTP = async () => {
    if (!mobile || mobile.length < 10) {
      toast.error('Enter a valid mobile number');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.sendOTP(mobile, 'forgot_password');
      setMockOtp(res.data.mock_otp || '');
      setOtpTimer(Math.floor(res.data.expires_in));
      setStep(2);
      toast.success('OTP sent to your mobile');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to send OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (otp.length !== 6) {
      toast.error('Enter 6-digit OTP');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.verifyOTP(mobile, otp, 'forgot_password');
      setOtpToken(res.data.otp_token);
      setStep(3);
      toast.success('OTP verified! Set your new password.');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (newPassword.length < 4) {
      toast.error('Password must be at least 4 characters');
      return;
    }
    setLoading(true);
    try {
      await authAPI.forgotPasswordReset(mobile, otpToken, newPassword);
      toast.success('Password reset successfully!');
      navigate('/login');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="p-3 bg-accent/20 rounded-xl">
            <KeyRound className="w-8 h-8 text-accent" />
          </div>
          <span className="text-2xl font-bold text-text-primary">SocietyHub</span>
        </div>

        <div className="card p-8">
          {step === 1 && (
            <>
              <h2 className="text-2xl font-bold text-text-primary mb-2">Forgot Password</h2>
              <p className="text-text-secondary mb-6">Enter your mobile number to receive OTP</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Mobile Number</label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input type="text" data-testid="forgot-mobile-input" value={mobile}
                      onChange={(e) => setMobile(e.target.value.replace(/\D/g, '').slice(0, 10))}
                      className="input-field w-full pl-10" placeholder="Enter registered mobile" maxLength={10} />
                  </div>
                </div>
                <button onClick={handleSendOTP} data-testid="forgot-send-otp-btn" disabled={loading}
                  className="btn-primary w-full py-3 disabled:opacity-50">
                  {loading ? 'Sending...' : 'Send OTP'}
                </button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <button onClick={() => setStep(1)} className="flex items-center gap-1 text-text-secondary hover:text-text-primary mb-4 text-sm">
                <ArrowLeft className="w-4 h-4" /> Back
              </button>
              <h2 className="text-xl font-bold text-text-primary mb-2">Verify OTP</h2>
              <p className="text-text-secondary text-sm mb-4">Sent to {mobile}</p>

              {mockOtp && (
                <div className="mb-4 p-3 bg-accent/10 border border-accent/30 rounded-lg">
                  <p className="text-accent text-sm font-medium">Test Mode - OTP: {mockOtp}</p>
                </div>
              )}

              <div className="space-y-4">
                <input type="text" data-testid="forgot-otp-input" value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="input-field w-full text-center text-2xl tracking-[0.5em] font-mono"
                  placeholder="------" maxLength={6} autoFocus />
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">
                    {otpTimer > 0 ? `Expires in ${Math.floor(otpTimer / 60)}:${String(otpTimer % 60).padStart(2, '0')}` : 'OTP expired'}
                  </span>
                </div>
                <button onClick={handleVerifyOTP} data-testid="forgot-verify-otp-btn" disabled={loading || otp.length !== 6}
                  className="btn-primary w-full py-3 disabled:opacity-50">
                  {loading ? 'Verifying...' : 'Verify OTP'}
                </button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="text-xl font-bold text-text-primary mb-2">Set New Password</h2>
              <p className="text-text-secondary text-sm mb-4">Create a new password for your account</p>
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">New Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input type={showPassword ? 'text' : 'password'} data-testid="forgot-new-password" value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="input-field w-full pl-10 pr-10" placeholder="4-20 characters" required />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary">
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">Confirm Password</label>
                  <input type="password" data-testid="forgot-confirm-password" value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="input-field w-full pl-10" placeholder="Confirm password" required />
                </div>
                <button type="submit" data-testid="forgot-reset-btn" disabled={loading}
                  className="btn-primary w-full py-3 disabled:opacity-50">
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
              </form>
            </>
          )}

          <div className="mt-6 text-center">
            <Link to="/login" className="text-accent hover:underline text-sm">Back to Login</Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export { Login, Register, RegisterAdmin, SetPassword, ForgotPassword };
