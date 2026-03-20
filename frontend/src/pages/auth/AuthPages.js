import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Building2, Eye, EyeOff, Phone, Lock, User, MapPin } from 'lucide-react';
import { authAPI } from '../../lib/api';
import useAuthStore from '../../store/authStore';
import { toast } from 'sonner';

const Login = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    mobile: '',
    password: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await authAPI.login(formData.mobile, formData.password);
      const { access_token, user } = response.data;
      
      setAuth(user, access_token);
      toast.success(`Welcome back, ${user.name}!`);
      
      // Redirect based on role
      switch (user.role) {
        case 'platform_owner':
          navigate('/platform');
          break;
        case 'admin':
          navigate('/admin');
          break;
        case 'sub_admin':
          navigate('/subadmin');
          break;
        case 'resident':
          navigate('/resident');
          break;
        default:
          navigate('/');
      }
    } catch (error) {
      const message = error.response?.data?.detail || 'Login failed';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-base flex">
      {/* Left side - Image */}
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
      
      {/* Right side - Form */}
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
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Mobile Number
                </label>
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
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Password
                </label>
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
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              
              <button
                type="submit"
                data-testid="login-submit-btn"
                disabled={loading}
                className="btn-primary w-full py-3 disabled:opacity-50"
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
            
            <div className="mt-6 text-center">
              <p className="text-text-secondary">
                Don't have an account?{' '}
                <Link to="/register" className="text-accent hover:underline" data-testid="register-link">
                  Register here
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
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [registerType, setRegisterType] = useState('resident'); // resident or admin
  const [formData, setFormData] = useState({
    mobile: '',
    name: '',
    email: '',
    password: '',
    societyName: '',
    societyAddress: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      if (registerType === 'admin') {
        await authAPI.registerAdmin(
          { mobile: formData.mobile, name: formData.name, email: formData.email, password: formData.password },
          formData.societyName,
          formData.societyAddress
        );
        toast.success('Admin registration submitted! Waiting for platform owner approval.');
      } else {
        await authAPI.register({
          mobile: formData.mobile,
          name: formData.name,
          email: formData.email,
          password: formData.password,
        });
        toast.success('Registration submitted! Waiting for admin approval.');
      }
      navigate('/login');
    } catch (error) {
      const message = error.response?.data?.detail || 'Registration failed';
      toast.error(message);
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
          <h2 className="text-2xl font-bold text-text-primary mb-2">Create Account</h2>
          <p className="text-text-secondary mb-6">Join your housing society</p>
          
          {/* Register Type Toggle */}
          <div className="flex gap-2 mb-6">
            <button
              type="button"
              onClick={() => setRegisterType('resident')}
              data-testid="register-type-resident"
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                registerType === 'resident' 
                  ? 'bg-accent text-white' 
                  : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              Resident
            </button>
            <button
              type="button"
              onClick={() => setRegisterType('admin')}
              data-testid="register-type-admin"
              className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                registerType === 'admin' 
                  ? 'bg-accent text-white' 
                  : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
              }`}
            >
              Society Admin
            </button>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Full Name
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type="text"
                  data-testid="register-name-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="input-field w-full pl-10"
                  placeholder="Enter your name"
                  required
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Mobile Number
              </label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type="text"
                  data-testid="register-mobile-input"
                  value={formData.mobile}
                  onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
                  className="input-field w-full pl-10"
                  placeholder="Enter mobile number"
                  required
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  data-testid="register-password-input"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="input-field w-full pl-10 pr-10"
                  placeholder="Create password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>
            
            {registerType === 'admin' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">
                    Society Name
                  </label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input
                      type="text"
                      data-testid="register-society-name-input"
                      value={formData.societyName}
                      onChange={(e) => setFormData({ ...formData, societyName: e.target.value })}
                      className="input-field w-full pl-10"
                      placeholder="Enter society name"
                      required
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-2">
                    Society Address
                  </label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                    <input
                      type="text"
                      data-testid="register-society-address-input"
                      value={formData.societyAddress}
                      onChange={(e) => setFormData({ ...formData, societyAddress: e.target.value })}
                      className="input-field w-full pl-10"
                      placeholder="Enter society address"
                      required
                    />
                  </div>
                </div>
              </>
            )}
            
            <button
              type="submit"
              data-testid="register-submit-btn"
              disabled={loading}
              className="btn-primary w-full py-3 disabled:opacity-50"
            >
              {loading ? 'Submitting...' : 'Register'}
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <p className="text-text-secondary">
              Already have an account?{' '}
              <Link to="/login" className="text-accent hover:underline" data-testid="login-link">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export { Login, Register };
