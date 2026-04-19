import React, { useState, useEffect } from 'react';
import { getMe, updateProfile, changePassword } from '../api';
import { User, Lock, Mail, CheckCircle2, AlertCircle, Save, XCircle, RefreshCw } from 'lucide-react';

const Profile = () => {
  const [profile, setProfile] = useState(null);
  const [username, setUsername] = useState('');
  const [passwords, setPasswords] = useState({ old: '', new: '', confirm: '' });
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState({ type: '', msg: '' });
  const [syncing, setSyncing] = useState({ username: false, password: false });

  useEffect(() => {
    fetchProfile();
  }, []);

  useEffect(() => {
    if (status.msg) {
      const timer = setTimeout(() => setStatus({ type: '', msg: '' }), 5000);
      return () => clearTimeout(timer);
    }
  }, [status]);

  const fetchProfile = async () => {
    try {
      const res = await getMe();
      setProfile(res.data);
      setUsername(res.data.username);
    } catch (err) {
      setStatus({ type: 'error', msg: 'Failed to load profile.' });
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateUsername = async (e) => {
    e.preventDefault();
    setStatus({ type: '', msg: '' });
    setSyncing(prev => ({ ...prev, username: true }));
    try {
      const res = await updateProfile({ username });
      setProfile(res.data);
      setStatus({ type: 'success', msg: 'Username updated successfully!' });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to update username.' });
    } finally {
      setSyncing(prev => ({ ...prev, username: false }));
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (passwords.new !== passwords.confirm) {
      setStatus({ type: 'error', msg: 'New passwords do not match.' });
      return;
    }
    setStatus({ type: '', msg: '' });
    setSyncing(prev => ({ ...prev, password: true }));
    try {
      await changePassword({ 
        old_password: passwords.old, 
        new_password: passwords.new 
      });
      setPasswords({ old: '', new: '', confirm: '' });
      setStatus({ type: 'success', msg: 'Password changed successfully!' });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to change password.' });
    } finally {
      setSyncing(prev => ({ ...prev, password: false }));
    }
  };

  if (loading) return <div className="flex-center" style={{ minHeight: '80vh' }}><div className="loader"></div></div>;

  return (
    <div className="container page-transition-enter" style={{ maxWidth: '800px', padding: '40px 20px' }}>
      <div className="flex items-center gap-4 mb-10">
        <div className="p-3 bg-blue-500/10 rounded-2xl">
          <User className="w-8 h-8 text-blue-500" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white">Profile Settings</h1>
          <p className="text-gray-400">Manage your account details and security</p>
        </div>
      </div>

      {/* Sync-style feedback */}
      {status.msg && (
        <div style={{
          background: status.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          borderLeft: `4px solid ${status.type === 'success' ? 'var(--success)' : 'var(--danger)'}`,
          color: status.type === 'success' ? 'var(--success)' : 'var(--danger)',
          padding: '16px',
          marginBottom: '32px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontSize: '15px',
          fontWeight: '500',
          animation: 'fadeIn 0.3s ease-out'
        }}>
          {status.type === 'success' ? <CheckCircle2 size={20} /> : <AlertCircle size={20} />}
          {status.msg}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Account Info */}
        <div className="glass-card p-8">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <Mail className="w-5 h-5 text-blue-400" />
            Account Information
          </h2>
          
          <form onSubmit={handleUpdateUsername} className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-400">Email Address</label>
              <input 
                type="text" 
                value={profile?.email} 
                disabled 
                className="input-field opacity-60 cursor-not-allowed bg-slate-800/50"
              />
              <p className="text-xs text-gray-500">Email cannot be changed.</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-400">Username</label>
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                placeholder="Enter new username"
              />
            </div>

            <button 
              type="submit" 
              className={`btn btn-primary w-full flex items-center justify-center gap-2 py-3 ${syncing.username ? 'opacity-70 cursor-not-allowed' : ''}`}
              disabled={syncing.username}
            >
              {syncing.username ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {syncing.username ? 'Updating...' : 'Update Username'}
            </button>
          </form>
        </div>

        {/* Security */}
        <div className="glass-card p-8">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <Lock className="w-5 h-5 text-amber-400" />
            Security
          </h2>
          
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-400">Current Password</label>
              <input 
                type="password" 
                value={passwords.old}
                onChange={(e) => setPasswords({...passwords, old: e.target.value})}
                className="input-field"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-400">New Password</label>
              <input 
                type="password" 
                value={passwords.new}
                onChange={(e) => setPasswords({...passwords, new: e.target.value})}
                className="input-field"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-400">Confirm New Password</label>
              <input 
                type="password" 
                value={passwords.confirm}
                onChange={(e) => setPasswords({...passwords, confirm: e.target.value})}
                className="input-field"
                required
              />
            </div>

            <button 
              type="submit" 
              className={`btn btn-secondary w-full py-3 mt-4 flex items-center justify-center gap-2 ${syncing.password ? 'opacity-70 cursor-not-allowed' : ''}`}
              disabled={syncing.password}
            >
              {syncing.password && <RefreshCw className="w-4 h-4 animate-spin" />}
              {syncing.password ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Profile;
