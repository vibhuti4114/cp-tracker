import React, { useEffect, useState } from 'react';
import { getAccounts, addAccount, syncAccount, deleteAccount } from '../api';
import { Plus, RefreshCw, CheckCircle2, XCircle, Trash2, AlertTriangle } from 'lucide-react';

// ─── Rating title helpers ──────────────────────────────────────────────────

const CODEFORCES_RANKS = [
  { min: 3000, title: 'Legendary Grandmaster', color: '#FF0000' },
  { min: 2600, title: 'International Grandmaster', color: '#FF3333' },
  { min: 2400, title: 'Grandmaster', color: '#FF3333' },
  { min: 2300, title: 'International Master', color: '#FFBB55' },
  { min: 2100, title: 'Master', color: '#FFBB55' },
  { min: 1900, title: 'Candidate Master', color: '#AA00AA' },
  { min: 1600, title: 'Expert', color: '#0000FF' },
  { min: 1400, title: 'Specialist', color: '#03A89E' },
  { min: 1200, title: 'Pupil', color: '#77FF77' },
  { min: 0,    title: 'Newbie', color: '#808080' },
];

const ATCODER_RANKS = [
  { min: 2800, title: 'Red', color: '#FF0000' },
  { min: 2400, title: 'Orange', color: '#FF8000' },
  { min: 2000, title: 'Yellow', color: '#C0C000' },
  { min: 1600, title: 'Blue', color: '#0000FF' },
  { min: 1200, title: 'Cyan', color: '#00C0C0' },
  { min: 800,  title: 'Green', color: '#008000' },
  { min: 400,  title: 'Brown', color: '#804000' },
  { min: 0,    title: 'Gray', color: '#808080' },
];

const CODECHEF_RANKS = [
  { min: 2500, title: '7★', color: '#FF7F00' },
  { min: 2200, title: '6★', color: '#FF7F00' },
  { min: 2000, title: '5★', color: '#3366CC' },
  { min: 1800, title: '4★', color: '#1A9FD9' },
  { min: 1600, title: '3★', color: '#684273' },
  { min: 1400, title: '2★', color: '#888800' },
  { min: 0,    title: '1★', color: '#999999' },
];

const LEETCODE_RANKS = [
  { min: 2200, title: 'Guardian', color: '#FFC800' },
  { min: 1850, title: 'Knight', color: '#C8A855' },
];

function getRatingTitle(platform, rating) {
  if (!rating) return null;
  let table;
  if (platform === 'codeforces') table = CODEFORCES_RANKS;
  else if (platform === 'atcoder')    table = ATCODER_RANKS;
  else if (platform === 'codechef')   table = CODECHEF_RANKS;
  else if (platform === 'leetcode')   table = LEETCODE_RANKS;
  else return null;

  for (const tier of table) {
    if (rating >= tier.min) return tier;
  }
  return null;
}

// ─── Component ────────────────────────────────────────────────────────────

const Accounts = () => {
  const [accounts, setAccounts]     = useState([]);
  const [platform, setPlatform]     = useState('codeforces');
  const [handle, setHandle]         = useState('');
  const [loading, setLoading]       = useState(true);
  const [adding, setAdding]         = useState(false);
  const [syncingId, setSyncingId]   = useState(null);
  const [removingId, setRemovingId] = useState(null);
  const [confirmId, setConfirmId]   = useState(null); // id pending confirmation
  const [error, setError]           = useState('');
  const [success, setSuccess]       = useState('');

  const fetchAccounts = async () => {
    try {
      const res = await getAccounts();
      setAccounts(res.data);
    } catch (err) {
      console.error('Failed to fetch accounts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAccounts(); }, []);

  const showMsg = (msg, isErr = false) => {
    isErr ? setError(msg) : setSuccess(msg);
    setTimeout(() => { setError(''); setSuccess(''); }, 5000);
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    setAdding(true);
    setError(''); setSuccess('');
    try {
      await addAccount(platform, handle);
      showMsg(`Successfully added ${platform} handle: ${handle}`);
      setHandle('');
      fetchAccounts();
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Failed to add account', true);
    } finally {
      setAdding(false);
    }
  };

  const handleSync = async (id) => {
    setSyncingId(id);
    setError(''); setSuccess('');
    try {
      await syncAccount(id);
      showMsg('Account synced successfully!');
      fetchAccounts();
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Failed to sync account', true);
    } finally {
      setSyncingId(null);
    }
  };

  const handleRemove = async (id) => {
    setRemovingId(id);
    setConfirmId(null);
    setError(''); setSuccess('');
    try {
      await deleteAccount(id);
      showMsg('Account removed successfully.');
      fetchAccounts();
    } catch (err) {
      showMsg(err.response?.data?.detail || 'Failed to remove account', true);
    } finally {
      setRemovingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex-center" style={{ minHeight: '60vh' }}>
        <div className="loader" style={{ width: '40px', height: '40px', borderWidth: '4px' }}></div>
      </div>
    );
  }

  return (
    <div className="container page-transition-enter" style={{ padding: '32px 24px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 className="heading-gradient" style={{ fontSize: '36px' }}>Platform Accounts</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Manage and sync your competitive programming handles.</p>
      </div>

      {/* Feedback banners */}
      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', borderLeft: '4px solid var(--danger)',
          color: 'var(--danger)', padding: '12px', marginBottom: '24px',
          borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <XCircle size={18} /> {error}
        </div>
      )}
      {success && (
        <div style={{
          background: 'rgba(16,185,129,0.1)', borderLeft: '4px solid var(--success)',
          color: 'var(--success)', padding: '12px', marginBottom: '24px',
          borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <CheckCircle2 size={18} /> {success}
        </div>
      )}

      <div className="grid-cols-2">
        {/* ── Add Account Form ─────────────────────────── */}
        <div className="glass-card">
          <h2 style={{ marginBottom: '24px', fontSize: '20px' }}>Add New Handle</h2>
          <form onSubmit={handleAdd}>
            <div>
              <label className="input-label">Platform</label>
              <select
                className="input-field"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                style={{ appearance: 'none', backgroundColor: 'rgba(15,23,42,0.8)' }}
              >
                <option value="codeforces">Codeforces</option>
                <option value="leetcode">LeetCode</option>
                <option value="codechef">CodeChef</option>
                <option value="atcoder">AtCoder</option>
              </select>
            </div>

            <div>
              <label className="input-label">Handle / Username</label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. tourist"
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="btn-primary full-width" disabled={adding}>
              {adding ? <div className="loader"></div> : <><Plus size={18} /> Add Account</>}
            </button>
          </form>
        </div>

        {/* ── Linked Accounts List ─────────────────────── */}
        <div>
          <h2 style={{ marginBottom: '24px', fontSize: '20px' }}>Your Linked Accounts</h2>
          {accounts.length === 0 ? (
            <div className="glass-card flex-center" style={{ minHeight: '150px', color: 'var(--text-muted)' }}>
              No accounts linked yet. Add one to get started!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {accounts.map(acc => {
                const rank = getRatingTitle(acc.platform, acc.current_rating);
                const isConfirming = confirmId === acc.id;
                const isSyncing    = syncingId === acc.id;
                const isRemoving   = removingId === acc.id;

                return (
                  <div key={acc.id} className="glass-card" style={{ padding: '20px' }}>
                    {/* Top row: platform + handle + actions */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '4px' }}>
                          <h3 style={{ textTransform: 'capitalize' }}>{acc.platform}</h3>
                          {/* Rating title badge */}
                          {rank && (
                            <span style={{
                              background: `${rank.color}22`,
                              border: `1px solid ${rank.color}66`,
                              color: rank.color,
                              padding: '2px 10px',
                              borderRadius: '20px',
                              fontSize: '11px',
                              fontWeight: '700',
                              letterSpacing: '0.03em',
                            }}>
                              {rank.title}
                            </span>
                          )}
                        </div>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                          Handle: <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{acc.handle}</span>
                        </p>
                        {acc.current_rating && (
                          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '2px' }}>
                            Rating: <span style={{ color: rank?.color || 'var(--text-primary)', fontWeight: '600' }}>
                              {Math.round(acc.current_rating)}
                            </span>
                            {acc.max_rating && (
                              <span style={{ color: 'var(--text-muted)' }}> · Peak: {Math.round(acc.max_rating)}</span>
                            )}
                          </p>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexShrink: 0 }}>
                        <button
                          onClick={() => handleSync(acc.id)}
                          className="btn-secondary"
                          disabled={isSyncing || isRemoving}
                          title="Sync this account"
                          style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}
                        >
                          {isSyncing
                            ? <div className="loader" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>
                            : <RefreshCw size={14} />
                          }
                          {isSyncing ? 'Syncing…' : 'Sync'}
                        </button>

                        {/* Remove — shows confirm prompt inline */}
                        {!isConfirming ? (
                          <button
                            onClick={() => setConfirmId(acc.id)}
                            disabled={isSyncing || isRemoving}
                            title="Remove this account"
                            style={{
                              padding: '8px 12px',
                              display: 'flex', alignItems: 'center', gap: '6px',
                              background: 'rgba(239,68,68,0.08)',
                              border: '1px solid rgba(239,68,68,0.3)',
                              borderRadius: '8px', color: 'var(--danger)',
                              fontSize: '13px', cursor: 'pointer',
                              transition: 'all 0.2s',
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(239,68,68,0.18)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'rgba(239,68,68,0.08)'}
                          >
                            <Trash2 size={14} /> Remove
                          </button>
                        ) : (
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <AlertTriangle size={14} color="var(--warning)" />
                            <span style={{ fontSize: '12px', color: 'var(--warning)', whiteSpace: 'nowrap' }}>Sure?</span>
                            <button
                              onClick={() => handleRemove(acc.id)}
                              disabled={isRemoving}
                              style={{
                                padding: '5px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: '600',
                                background: 'var(--danger)', border: 'none', color: '#fff', cursor: 'pointer',
                              }}
                            >
                              {isRemoving ? '…' : 'Yes'}
                            </button>
                            <button
                              onClick={() => setConfirmId(null)}
                              style={{
                                padding: '5px 10px', borderRadius: '6px', fontSize: '12px', fontWeight: '600',
                                background: 'rgba(255,255,255,0.08)', border: '1px solid var(--border-light)',
                                color: 'var(--text-secondary)', cursor: 'pointer',
                              }}
                            >
                              No
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Footer: last synced */}
                    {acc.last_synced_at && (
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '14px' }}>
                        Last synced: {new Date(acc.last_synced_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Accounts;
