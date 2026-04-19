import React, { useEffect, useState, useCallback } from 'react';
import { getAnalytics, getRatingHistory, getAccounts, syncAllAccounts, getUserByUsername } from '../api';
import { useParams } from 'react-router-dom';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { Activity, Trophy, Code2, Target, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';

const PLATFORM_COLORS = {
  codeforces: '#3b82f6',
  leetcode:   '#f59e0b',
  codechef:   '#8b5cf6',
  atcoder:    '#10b981',
};

// ─── Rating title helpers ─────────────────────────────────────────────────
const CODEFORCES_RANKS = [
  { min: 3000, title: 'Legendary Grandmaster', color: '#FF0000' },
  { min: 2600, title: 'International Grandmaster', color: '#FF3333' },
  { min: 2400, title: 'Grandmaster', color: '#FF3333' },
  { min: 2300, title: 'International Master', color: '#FFBB55' },
  { min: 2100, title: 'Master', color: '#FFBB55' },
  { min: 1900, title: 'Candidate Master', color: '#AA00AA' },
  { min: 1600, title: 'Expert', color: '#5555FF' },
  { min: 1400, title: 'Specialist', color: '#03A89E' },
  { min: 1200, title: 'Pupil', color: '#77BB77' },
  { min: 0,    title: 'Newbie', color: '#888888' },
];
const ATCODER_RANKS = [
  { min: 2800, title: 'Red', color: '#FF0000' },
  { min: 2400, title: 'Orange', color: '#FF8000' },
  { min: 2000, title: 'Yellow', color: '#C0C000' },
  { min: 1600, title: 'Blue', color: '#4488FF' },
  { min: 1200, title: 'Cyan', color: '#00C0C0' },
  { min: 800,  title: 'Green', color: '#44AA44' },
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
const RANK_TABLES = { codeforces: CODEFORCES_RANKS, atcoder: ATCODER_RANKS, codechef: CODECHEF_RANKS, leetcode: LEETCODE_RANKS };

function getRatingRank(platform, rating) {
  if (!rating) return null;
  const table = RANK_TABLES[platform];
  if (!table) return null;
  for (const tier of table) {
    if (rating >= tier.min) return tier;
  }
  return null;
}

const RatingTooltip = ({ active, payload, lineColor }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    const isPositive = data.change >= 0;

    return (
      <div style={{
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        backdropFilter: 'blur(8px)',
        border: '1px solid var(--border-light)',
        borderRadius: '12px',
        padding: '16px',
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.4)',
        minWidth: '220px',
      }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '11px', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {data.fullDate}
        </p>
        <h4 style={{ color: '#fff', fontSize: '15px', marginBottom: '12px', lineHeight: '1.4' }}>
          {data.contest}
        </h4>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>New Rating</span>
          <span style={{ color: lineColor, fontWeight: '700', fontSize: '16px' }}>{Math.round(data.rating)}</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Change</span>
          <span style={{ color: isPositive ? 'var(--success)' : 'var(--danger)', fontWeight: '600', fontSize: '13px' }}>
            {isPositive ? '▲' : '▼'} {Math.abs(Math.round(data.change))}
          </span>
        </div>

        {data.rank && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px', marginTop: '8px' }}>
            <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Rank</span>
            <span style={{ color: '#fff', fontWeight: '600', fontSize: '13px' }}>#{data.rank}</span>
          </div>
        )}
      </div>
    );
  }
  return null;
};

const Dashboard = () => {
  const { username } = useParams();
  const [analytics, setAnalytics]   = useState(null);
  const [accounts, setAccounts]     = useState([]);
  const [allHistory, setAllHistory] = useState([]);   // full dataset for all accounts
  const [chartData, setChartData]   = useState([]);
  const [selectedId, setSelectedId] = useState(null); // null = show all
  const [loading, setLoading]       = useState(true);
  const [syncing, setSyncing]       = useState(false);
  const [syncMsg, setSyncMsg]       = useState('');
  const [syncErr, setSyncErr]       = useState('');
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [profileUser, setProfileUser] = useState(null);

  const buildChartData = useCallback((history, accountId) => {
    const filtered = accountId
      ? history.filter(e => e.account_id === accountId)
      : history;

    return [...filtered]
      .sort((a, b) => new Date(a.participated_at) - new Date(b.participated_at))
      .map(entry => ({
        date:       new Date(entry.participated_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }),
        fullDate:   new Date(entry.participated_at).toLocaleDateString('en-GB', { weekday:'short', day:'2-digit', month:'long', year:'numeric' }),
        rating:     entry.new_rating,
        oldRating:  entry.old_rating,
        change:     entry.new_rating - entry.old_rating,
        platform:   entry.platform,
        contest:    entry.contest_name,
        rank:       entry.rank,
      }));
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        let userId = null;
        if (username) {
          const userRes = await getUserByUsername(username);
          userId = userRes.data.id;
          setProfileUser(userRes.data);
          setIsReadOnly(true);
        }

        const [analyticsRes, historyRes] = await Promise.all([
          getAnalytics(userId),
          getRatingHistory(userId ? { target_user_id: userId } : {}),
        ]);

        setAnalytics(analyticsRes.data);
        setAllHistory(historyRes.data);
        setChartData(buildChartData(historyRes.data, null));
        
        // We only show account tabs/cards if we have analytics platforms
        const platforms = analyticsRes.data.platforms || {};
        const accs = Object.entries(platforms).map(([platform, data], index) => ({
          id: index + 1, // temporary ID for filtering if actual account_id is not in platform_stats
          platform,
          handle: data.handle,
          ...data
        }));
        setAccounts(accs);

      } catch (err) {
        console.error('Fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [username, buildChartData]);

  const handleSelectAccount = (accountId) => {
    const newId = selectedId === accountId ? null : accountId;
    setSelectedId(newId);
    setChartData(buildChartData(allHistory, newId));
  };

  const handleSyncAll = async () => {
    setSyncing(true);
    setSyncMsg('');
    setSyncErr('');
    try {
      const res = await syncAllAccounts();
      const succeeded = res.data.filter(r => r.status === 'success').length;
      setSyncMsg(`Synced ${succeeded}/${res.data.length} accounts successfully!`);
      // Refresh data
      const [analyticsRes, historyRes, accountsRes] = await Promise.all([
        getAnalytics(),
        getRatingHistory({}),
        getAccounts(),
      ]);
      setAnalytics(analyticsRes.data);
      setAccounts(accountsRes.data);
      const hist = historyRes.data;
      setAllHistory(hist);
      setChartData(buildChartData(hist, selectedId));
    } catch (err) {
      setSyncErr(err.response?.data?.detail || 'Failed to sync accounts.');
    } finally {
      setSyncing(false);
      setTimeout(() => { setSyncMsg(''); setSyncErr(''); }, 5000);
    }
  };

  if (loading) {
    return (
      <div className="flex-center" style={{ minHeight: '60vh' }}>
        <div className="loader" style={{ width: '40px', height: '40px', borderWidth: '4px' }}></div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="container">
        <div className="glass-card" style={{ textAlign: 'center', padding: '48px' }}>
          <h2>No Data Available</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
            Please add your CP platform handles in the Accounts section.
          </p>
        </div>
      </div>
    );
  }

  // Active account info for graph header
  const activeAccount = accounts.find(a => a.id === selectedId);
  const graphTitle = activeAccount
    ? `${activeAccount.platform.charAt(0).toUpperCase() + activeAccount.platform.slice(1)} — ${activeAccount.handle}`
    : 'All Platforms';
  const lineColor = activeAccount
    ? (PLATFORM_COLORS[activeAccount.platform] || 'var(--accent-primary)')
    : 'var(--accent-primary)';

  return (
    <div className="container page-transition-enter" style={{ padding: '32px 24px' }}>
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {isReadOnly ? `${profileUser?.username}'s Profile` : 'Dashboard'}
          </h1>
          <p className="text-gray-400">
            {isReadOnly ? `Viewing stats for ${profileUser?.username}` : 'Welcome back! Here\'s your competitive programming summary.'}
          </p>
        </div>
        
        {!isReadOnly && (
          <button 
            onClick={handleSyncAll}
            disabled={syncing}
            className={`btn btn-primary flex items-center gap-2 ${syncing ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Syncing...' : 'Sync All'}
          </button>
        )}
      </div>

      {/* Sync feedback */}
      {syncMsg && (
        <div style={{
          background: 'rgba(16, 185, 129, 0.1)', borderLeft: '4px solid var(--success)',
          color: 'var(--success)', padding: '12px', marginBottom: '24px', borderRadius: '4px',
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <CheckCircle2 size={18} /> {syncMsg}
        </div>
      )}
      {syncErr && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.1)', borderLeft: '4px solid var(--danger)',
          color: 'var(--danger)', padding: '12px', marginBottom: '24px', borderRadius: '4px',
          display: 'flex', alignItems: 'center', gap: '8px'
        }}>
          <XCircle size={18} /> {syncErr}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid-cols-2" style={{ marginBottom: '32px' }}>
        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(59, 130, 246, 0.2)', padding: '16px', borderRadius: '12px', color: 'var(--accent-primary)' }}>
            <Code2 size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', fontWeight: '500' }}>Total Problems Solved</p>
            <h3 style={{ fontSize: '28px', margin: '4px 0 0 0' }}>{analytics.total_problems_solved}</h3>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'rgba(139, 92, 246, 0.2)', padding: '16px', borderRadius: '12px', color: 'var(--accent-secondary)' }}>
            <Target size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', fontWeight: '500' }}>Total Contests</p>
            <h3 style={{ fontSize: '28px', margin: '4px 0 0 0' }}>{analytics.total_contests}</h3>
          </div>
        </div>
      </div>

      {/* Rating Graph */}
      <div className="glass-card" style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
            <Activity size={20} color="var(--accent-primary)" /> Rating History
            <span style={{ fontSize: '14px', fontWeight: '400', color: 'var(--text-secondary)', marginLeft: '8px' }}>
              — {graphTitle}
            </span>
          </h2>
          {selectedId && (
            <button
              onClick={() => handleSelectAccount(null)}
              style={{
                background: 'rgba(255,255,255,0.08)', border: '1px solid var(--border-light)',
                borderRadius: '20px', padding: '4px 14px', fontSize: '12px', color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              Show All ✕
            </button>
          )}
        </div>

        {/* Platform filter pills */}
        {accounts.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
            {accounts.map(acc => (
              <button
                key={acc.id}
                onClick={() => handleSelectAccount(acc.id)}
                style={{
                  background: selectedId === acc.id
                    ? (PLATFORM_COLORS[acc.platform] || 'var(--accent-primary)')
                    : 'rgba(255,255,255,0.07)',
                  border: `1px solid ${selectedId === acc.id ? 'transparent' : 'var(--border-light)'}`,
                  borderRadius: '20px',
                  padding: '6px 16px',
                  fontSize: '13px',
                  fontWeight: '600',
                  color: selectedId === acc.id ? '#fff' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  textTransform: 'capitalize',
                }}
              >
                {acc.platform} · {acc.handle}
              </button>
            ))}
          </div>
        )}

        {chartData.length > 0 ? (
          <div style={{ width: '100%', height: '350px' }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="date" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)' }} domain={['auto', 'auto']} />
                <Tooltip content={<RatingTooltip lineColor={lineColor} />} />
                <Line
                  type="monotone"
                  dataKey="rating"
                  stroke={lineColor}
                  strokeWidth={3}
                  dot={{ r: 4, fill: 'var(--bg-primary)', strokeWidth: 2, stroke: lineColor }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex-center" style={{ height: '200px', color: 'var(--text-muted)' }}>
            No rating history for this selection.
          </div>
        )}
      </div>

      {/* Platform Breakdown — click a card to see its graph */}
      <h2 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Trophy size={20} color="var(--warning)" /> Platform Breakdown
        <span style={{ fontSize: '13px', fontWeight: '400', color: 'var(--text-muted)', marginLeft: '4px' }}>
          (tap a card to filter the graph)
        </span>
      </h2>
      <div className="grid-cols-2">
        {analytics.platforms?.map((platform) => {
          const matchedAccount = accounts.find(
            a => a.platform === platform.platform && a.handle === platform.handle
          );
          const isSelected = matchedAccount && selectedId === matchedAccount.id;
          const accentColor = PLATFORM_COLORS[platform.platform] || 'var(--accent-primary)';

          return (
            <div
              key={platform.platform + platform.handle}
              className="glass-card"
              onClick={() => matchedAccount && handleSelectAccount(matchedAccount.id)}
              style={{
                cursor: matchedAccount ? 'pointer' : 'default',
                outline: isSelected ? `2px solid ${accentColor}` : '2px solid transparent',
                transition: 'outline 0.2s ease, transform 0.15s ease',
                transform: isSelected ? 'scale(1.02)' : 'scale(1)',
              }}
            >
              {/* Card header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <h3 style={{ textTransform: 'capitalize', color: isSelected ? accentColor : 'inherit', marginBottom: '4px' }}>
                    {platform.platform}
                  </h3>
                  {/* Rank badge */}
                  {(() => {
                    const rank = getRatingRank(platform.platform, platform.current_rating);
                    return rank ? (
                      <span style={{
                        display: 'inline-block',
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
                    ) : null;
                  })()}
                </div>
                <span style={{
                  background: isSelected ? accentColor : 'rgba(255,255,255,0.1)',
                  color: isSelected ? '#fff' : 'var(--text-secondary)',
                  padding: '4px 12px',
                  borderRadius: '20px',
                  fontSize: '12px',
                  fontWeight: '600',
                  transition: 'all 0.2s',
                  whiteSpace: 'nowrap',
                }}>
                  {platform.handle}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}>Current Rating</p>
                  <p style={{ fontSize: '18px', fontWeight: '600', color: platform.current_rating ? accentColor : 'var(--text-muted)' }}>
                    {platform.current_rating ? Math.round(platform.current_rating) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}>Max Rating</p>
                  <p style={{ fontSize: '18px', fontWeight: '600', color: platform.max_rating ? 'var(--success)' : 'var(--text-muted)' }}>
                    {platform.max_rating ? Math.round(platform.max_rating) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}>Problems Solved</p>
                  <p style={{ fontSize: '18px', fontWeight: '600' }}>{platform.problems_solved || 0}</p>
                </div>
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginBottom: '4px' }}>Contests</p>
                  <p style={{ fontSize: '18px', fontWeight: '600' }}>{platform.contests_participated || 0}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Dashboard;
