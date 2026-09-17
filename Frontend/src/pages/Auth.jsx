import { useState } from 'react';
import { loginUser, registerUser } from '../services/authApi';

export default function Auth({ onLogin }) {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      let data;
      if (isLogin) {
        data = await loginUser(formData.email, formData.password);
      } else {
        data = await registerUser(formData.name, formData.email, formData.password);
      }
      
      if (data.success) {
        localStorage.setItem('token', data.data.token);
        onLogin(data.data);
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#020617] text-slate-100 z-50 relative">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(15,23,42,1)_0%,rgba(2,6,23,1)_100%)] z-[-1]" />
      
      <div className="bg-[#0f172a]/80 backdrop-blur-md p-8 rounded-2xl border border-[#1e293b] shadow-2xl w-full max-w-md">
        <h2 className="text-3xl font-bold mb-6 text-center text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-300">
          {isLogin ? 'Welcome Back' : 'Create Account'}
        </h2>
        
        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-3 rounded-lg mb-4 text-sm text-center">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1">Name</label>
              <input 
                type="text"
                required={!isLogin}
                className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-400 transition-colors"
                value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
              />
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Email</label>
            <input 
              type="email"
              required
              className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-400 transition-colors"
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Password</label>
            <input 
              type="password"
              required
              className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-400 transition-colors"
              value={formData.password}
              onChange={e => setFormData({...formData, password: e.target.value})}
            />
          </div>
          
          <button 
            type="submit" 
            disabled={loading}
            className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-semibold py-2 px-4 rounded-lg transition-all duration-200 shadow-[0_0_15px_rgba(0,242,255,0.3)] disabled:opacity-50"
          >
            {loading ? 'Processing...' : (isLogin ? 'Login' : 'Register')}
          </button>
        </form>
        
        <p className="mt-6 text-center text-slate-400 text-sm">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <button 
            type="button"
            className="text-cyan-400 hover:text-cyan-300 font-medium"
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
          >
            {isLogin ? 'Sign up' : 'Log in'}
          </button>
        </p>
      </div>
    </div>
  );
}
