import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Mail, Lock, ArrowRight, Info } from 'lucide-react';

const DEMO_CREDENTIALS = [
  { role: 'Consumer', email: 'consumer@dpe.com', password: 'Consumer123!', icon: '👤' },
  { role: 'Admin', email: 'admin@dpe.com', password: 'Admin123!', icon: '⚙️' },
  { role: 'Business', email: 'business@dpe.com', password: 'Business123!', icon: '💼' },
  { role: 'Support', email: 'support@dpe.com', password: 'Support123!', icon: '🎧' },
];

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleQuickLogin = async (demoEmail: string, demoPassword: string) => {
    setLoading(true);
    setError('');
    try {
      await login(demoEmail, demoPassword);
      navigate('/vehicles');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      navigate('/vehicles');
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden" style={{ backgroundColor: 'var(--bg-primary)' }}>
      {/* Background Effects */}
      <div className="absolute inset-0 bg-grid opacity-20" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-[120px]" />

      <div className="card w-full max-w-md relative z-10 animate-scale-in">
        {/* Logo & Header */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-3 mb-6">
            <img 
              src="/teclusion.png" 
              alt="Dynamic Pricing Engine" 
              className="h-12 w-12 object-contain"
            />
            <span className="text-xl font-bold text-theme-primary">Dynamic Pricing Engine</span>
          </Link>
          <h1 className="text-2xl font-bold text-theme-primary mb-2">Welcome Back</h1>
          <p className="text-theme-secondary">Sign in to continue to your account</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-xl text-sm animate-fade-in">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-theme-secondary mb-2">Email</label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-theme-muted" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input pl-12"
                placeholder="Enter your email"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-theme-secondary mb-2">Password</label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-theme-muted" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input pl-12"
                placeholder="Enter your password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-3.5 justify-center"
          >
            {loading ? (
              <span className="flex items-center">
                <svg className="animate-spin -ml-1 mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Signing in...
              </span>
            ) : (
              <span className="flex items-center">
                Sign In
                <ArrowRight className="ml-2 h-5 w-5" />
              </span>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="relative my-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full" style={{ borderTop: '1px solid var(--border-color)' }} />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 text-theme-muted" style={{ backgroundColor: 'var(--bg-card)' }}>Quick Demo Access</span>
          </div>
        </div>

        {/* Quick Login Buttons */}
        <div className="grid grid-cols-2 gap-3">
          {DEMO_CREDENTIALS.map((cred) => (
            <button
              key={cred.role}
              onClick={() => handleQuickLogin(cred.email, cred.password)}
              disabled={loading}
              className="btn-secondary text-sm py-3 justify-center group"
            >
              <span className="mr-2">{cred.icon}</span>
              {cred.role}
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-8 pt-6 text-center" style={{ borderTop: '1px solid var(--border-color)' }}>
          <p className="text-theme-muted text-sm flex items-center justify-center gap-2">
            <Info className="h-4 w-4" />
            Demo Environment - Click any role to auto-login
          </p>
        </div>
      </div>
    </div>
  );
}
