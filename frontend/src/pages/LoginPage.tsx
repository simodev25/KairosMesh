import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { Lock } from 'lucide-react';

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState('admin@local.dev');
  const [password, setPassword] = useState('admin1234');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="hw-surface w-full max-w-sm p-8">
        {/* Brand */}
        <div className="flex flex-col items-center gap-4 mb-8">
          <img
            src="/kairos_mesh_logo.svg"
            alt="Kairos Mesh"
            className="w-48 h-auto"
          />
          <span className="text-[9px] text-text-dim tracking-[0.14em] uppercase block">
            AUTHENTICATION_REQUIRED
          </span>
        </div>

        {/* Form */}
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div>
            <label className="micro-label block mb-2">EMAIL_ID</label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              type="email"
              required
            />
          </div>
          <div>
            <label className="micro-label block mb-2">ACCESS_KEY</label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
            />
          </div>
          {error && <div className="alert">{error}</div>}
          <button className="btn-primary w-full mt-2" disabled={loading}>
            <Lock className="w-3.5 h-3.5" />
            {loading ? 'CONNECTING...' : 'INITIALIZE_SESSION'}
          </button>
        </form>

        {/* Footer */}
        <div className="flex items-center justify-center gap-2 mt-6">
          <div className="led led-blue" />
          <span className="text-[8px] text-text-dim tracking-[0.14em] uppercase">
            SECURE_LINK // v4.2
          </span>
        </div>
      </div>
    </div>
  );
}
