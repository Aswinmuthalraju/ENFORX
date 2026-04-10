import React, { useState, useEffect, useRef } from 'react';
import Navbar from '../components/Navbar';
import { Send, X, MessageSquare, LayoutDashboard, Briefcase, Settings2, Loader2, RefreshCw } from 'lucide-react';

// ── Layer definitions ─────────────────────────────────────────────────────────
const LAYERS = [
  { id: 1,  key: 'l1_firewall',     name: 'EnforxGuard Input Firewall',          desc: 'Sanitize and taint-tag incoming prompt' },
  { id: 2,  key: 'l2_ife',          name: 'Intent Formalization Engine',          desc: 'Parse user intent to formal SID logic' },
  { id: 3,  key: 'l3_grc',          name: 'Guided Reasoning Constraints',         desc: 'GRC fence — governance & compliance bounds' },
  { id: 4,  key: 'l4_deliberation', name: 'Agent Core (Multi-Agent)',             desc: 'Multi-agent deliberation + leader decision' },
  { id: 5,  key: 'l5_piav',         name: 'Plan-Intent Alignment Validator',      desc: 'Verify plan matches formalized intent' },
  { id: 6,  key: 'l6_ccv',          name: 'Causal Chain Validator',               desc: 'Causal chain + portfolio stress test' },
  { id: 7,  key: 'l7_fdee',         name: 'FDEE (Safety Controller)',             desc: 'Financial domain enforcement engine' },
  { id: 8,  key: 'l8_dap',          name: 'Delegation Authority Protocol',        desc: 'Delegation token & authority verification' },
  { id: 9,  key: 'l9_output',       name: 'EnforxGuard Output Firewall → Alpaca', desc: 'Secure Alpaca execution dispatch' },
  { id: 10, key: 'audit',           name: 'Adaptive Audit Loop',                  desc: 'Immutable hash-chained state capture' },
];

// Map status strings to display colors
function StatusBadge({ status }) {
  const map = {
    PASS:                'bg-green-500/30 text-green-300 border-green-400/50',
    ALLOW:               'bg-green-500/30 text-green-300 border-green-400/50',
    ALIGNED:             'bg-green-500/30 text-green-300 border-green-400/50',
    PROCEED:             'bg-green-500/30 text-green-300 border-green-400/50',
    AUTHORIZED:          'bg-green-500/30 text-green-300 border-green-400/50',
    BUILT:               'bg-green-500/30 text-green-300 border-green-400/50',
    SUCCESS:             'bg-green-500/30 text-green-300 border-green-400/50',
    BLOCK:               'bg-red-500/30 text-red-300 border-red-400/50',
    MISALIGNED:          'bg-red-500/30 text-red-300 border-red-400/50',
    EMERGENCY_BLOCK:     'bg-red-500/30 text-red-300 border-red-400/50',
    DELEGATION_VIOLATION:'bg-red-500/30 text-red-300 border-red-400/50',
    FLAG:                'bg-orange-500/30 text-orange-300 border-orange-400/50',
    CORRECT:             'bg-purple-500/30 text-purple-300 border-purple-400/50',
    MODIFY:              'bg-purple-500/30 text-purple-300 border-purple-400/50',
  };
  const cls = map[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  const label = status === 'BUILT' ? 'PASS' : status;
  return (
    <span className={`px-2 py-1 text-xs font-bold rounded-md border shadow-sm ${cls}`}>
      {label}
    </span>
  );
}

// Derive per-layer status from pipeline result
function getLayerStatus(layer, pipelineResult) {
  if (!pipelineResult) return null;

  // Use real layer_results if available
  const lr = pipelineResult.layer_results || {};
  if (layer.key === 'audit') {
    return pipelineResult.audit_entry_id ? 'PASS' : (pipelineResult.status === 'SUCCESS' ? 'PASS' : null);
  }
  const entry = lr[layer.key];
  if (entry) {
    const s = entry.status;
    if (!s) return null;
    // Normalize GRC "BUILT" → PASS
    return s === 'BUILT' ? 'PASS' : s;
  }

  // Fallback: derive from blocked_at / status
  if (pipelineResult.status === 'SUCCESS') return 'PASS';
  const blockedMap = {
    BLOCKED_L1: 1, BLOCKED_L2: 2, BLOCKED_L4: 4,
    BLOCKED_L5: 5, BLOCKED_L6: 6, BLOCKED_L7: 7,
    BLOCKED_L8: 8, BLOCKED_L9: 9, BLOCKED_LEADER_OVERRIDE: 4,
    ERROR: 1,
  };
  const blockedAt = blockedMap[pipelineResult.status];
  if (blockedAt != null) {
    if (layer.id < blockedAt) return 'PASS';
    if (layer.id === blockedAt) return 'BLOCK';
  }
  return null;
}

function fmt(n) {
  if (n == null || isNaN(Number(n))) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ── Main component ────────────────────────────────────────────────────────────
export default function SystemConsole() {
  const [drawerOpen, setDrawerOpen]         = useState(false);
  const [activeView, setActiveView]         = useState('Dashboard');
  const [input, setInput]                   = useState('');
  const [messages, setMessages]             = useState([]);
  const [loading, setLoading]               = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [activeLayerIdx, setActiveLayerIdx] = useState(-1);   // 0-9 while loading
  const [portfolio, setPortfolio]           = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);
  const chatEndRef  = useRef(null);
  const animTimerRef = useRef(null);

  const fetchPortfolio = () => {
    setPortfolioLoading(true);
    fetch('/api/portfolio')
      .then(r => r.json())
      .then(data => setPortfolio(data))
      .catch(err => setPortfolio({ account: { error: err.message }, positions: [] }))
      .finally(() => setPortfolioLoading(false));
  };

  useEffect(() => { fetchPortfolio(); }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Layer animation while pipeline runs
  useEffect(() => {
    if (loading) {
      setActiveLayerIdx(0);
      animTimerRef.current = setInterval(() => {
        setActiveLayerIdx(i => (i < 9 ? i + 1 : 9));
      }, 700);
    } else {
      clearInterval(animTimerRef.current);
      setActiveLayerIdx(-1);
    }
    return () => clearInterval(animTimerRef.current);
  }, [loading]);

  const sendCommand = async () => {
    const cmd = input.trim();
    if (!cmd || loading) return;

    setMessages(m => [...m, { role: 'user', text: cmd }]);
    setInput('');
    setLoading(true);
    setPipelineResult(null);

    try {
      const res  = await fetch('/api/pipeline', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ command: cmd }),
      });
      const data = await res.json();
      setPipelineResult(data);

      const isBlocked  = data.status && data.status !== 'SUCCESS';
      const execResult = data.execution_result;
      const leaderDec  = data.leader_decision;

      let responseText = '';
      if (isBlocked) {
        responseText = `Blocked at ${data.blocked_at || data.status}.`;
        if (leaderDec?.reasons?.length) {
          responseText += ' ' + leaderDec.reasons.slice(0, 2).join(' ');
        }
      } else if (execResult?.status === 'NO_TRADE') {
        responseText = 'Analysis complete. No trade action required.';
      } else if (execResult?.status === 'SUBMITTED' || execResult?.status === 'EXECUTED') {
        responseText = `Trade executed: ${execResult.side?.toUpperCase()} ${execResult.qty} ${execResult.symbol} — Order ${execResult.order_id}.`;
      } else if (execResult?.status === 'ERROR') {
        responseText = `Trade error: ${execResult.error}`;
      } else {
        responseText = `Pipeline completed: ${data.status}`;
      }

      setMessages(m => [...m, {
        role: 'enforx',
        text: responseText,
        status: isBlocked ? 'BLOCK' : 'SUCCESS',
        execResult,
      }]);

      // Refresh portfolio after trade
      if (execResult?.status === 'SUBMITTED') {
        setTimeout(fetchPortfolio, 2000);
      }
    } catch (err) {
      setMessages(m => [...m, { role: 'enforx', text: 'API error: ' + err.message, status: 'BLOCK' }]);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendCommand(); }
  };

  const navigateTo = view => { setActiveView(view); setDrawerOpen(false); };

  const drawerCls = view => {
    const isActive = activeView === view || (activeView === 'Dashboard' && ['Chat', 'Pipeline'].includes(view));
    return `flex items-center gap-3 w-full px-5 py-3.5 mt-1 transition-colors cursor-pointer rounded-lg text-sm ${
      isActive ? 'bg-accent text-foreground font-bold' : 'text-muted-foreground hover:bg-secondary hover:text-foreground font-medium'
    }`;
  };

  // ── Sub-panels ──────────────────────────────────────────────────────────────

  const renderChat = (widthClass) => (
    <section className={`bg-card rounded-xl border border-border flex flex-col overflow-hidden shadow-sm shrink-0 h-full w-full ${widthClass}`}>
      <header className="p-6 border-b border-border bg-card z-10 shrink-0">
        <h2 className="text-xl font-semibold text-foreground">Session</h2>
      </header>

      <div className="flex-1 px-8 py-8 overflow-y-auto space-y-8 custom-scrollbar bg-card">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-2">
            <MessageSquare size={32} strokeWidth={1.5} />
            <p className="text-sm font-medium">Send a trade command to begin</p>
            <p className="text-xs opacity-70">e.g. "Buy 5 shares of AAPL"</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="flex flex-col gap-2 items-start">
            <span className={`text-xs font-bold uppercase tracking-wider ${msg.role === 'user' ? 'text-muted-foreground' : 'text-primary'}`}>
              {msg.role === 'user' ? 'User' : 'Enforx Kernel'}
            </span>
            {msg.role === 'user' ? (
              <div className="bg-secondary p-5 rounded-xl text-sm text-foreground w-full border border-border leading-relaxed">
                {msg.text}
              </div>
            ) : (
              <div className="bg-primary p-5 rounded-xl text-sm text-primary-foreground w-full shadow-md leading-relaxed">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <span className={`px-2 py-0.5 text-[10px] font-black rounded border ${
                    msg.status === 'BLOCK'
                      ? 'bg-red-500/40 border-red-400/60 text-red-200'
                      : 'bg-green-500/40 border-green-400/60 text-green-200'
                  }`}>{msg.status}</span>
                  {msg.execResult?.status === 'SUBMITTED' && (
                    <span className="px-2 py-0.5 text-[10px] font-black rounded border bg-blue-500/40 border-blue-400/60 text-blue-200">ORDER SUBMITTED</span>
                  )}
                </div>
                <p className="opacity-90">{msg.text}</p>
                {msg.execResult?.order_id && (
                  <div className="mt-3 bg-black/20 p-3 rounded-lg text-xs font-mono text-primary-foreground border border-black/10">
                    {msg.execResult.side?.toUpperCase()} {msg.execResult.qty} {msg.execResult.symbol} @ {msg.execResult.type || 'MKT'} | ID: {msg.execResult.order_id}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex flex-col gap-2 items-start">
            <span className="text-xs font-bold uppercase tracking-wider text-primary">Enforx Kernel</span>
            <div className="bg-primary p-5 rounded-xl text-sm text-primary-foreground w-full shadow-md flex items-center gap-3">
              <Loader2 size={16} className="animate-spin shrink-0" />
              <span className="opacity-80">Running 10-layer safety pipeline…</span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="p-5 border-t border-border bg-muted flex gap-3 items-center shrink-0">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
          className="flex-1 bg-background border border-border rounded-lg px-5 py-3 lg:py-4 text-sm focus:outline-none focus:ring-2 focus:ring-ring text-foreground placeholder-muted-foreground disabled:opacity-50"
          placeholder="Enter command…"
        />
        <button
          onClick={sendCommand}
          disabled={loading || !input.trim()}
          className="px-5 py-3 lg:py-4 bg-primary text-primary-foreground font-semibold rounded-lg hover:opacity-90 transition-opacity whitespace-nowrap text-sm disabled:opacity-40 flex items-center gap-2"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          Send
        </button>
      </div>
    </section>
  );

  const renderPipeline = (widthClass) => (
    <section className={`bg-card rounded-xl border border-border flex flex-col overflow-hidden shadow-sm shrink-0 h-full w-full relative ${widthClass}`}>
      <header className="p-6 border-b border-border flex justify-between items-center bg-muted shrink-0">
        <div className="w-full">
          <h2 className="text-xl font-semibold text-center text-foreground">Execution Pipeline</h2>
          <p className="text-sm text-muted-foreground text-center font-medium mt-1">
            {loading
              ? `Processing layer ${activeLayerIdx + 1} of 10…`
              : pipelineResult
                ? `Result: ${pipelineResult.status}`
                : 'Awaiting command'}
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto w-full relative custom-scrollbar bg-card">
        <div className="flex flex-col gap-3 p-5 max-w-2xl mx-auto pb-8">
          {LAYERS.map((layer, idx) => {
            const status   = getLayerStatus(layer, pipelineResult);
            const isActive = loading && activeLayerIdx === idx;
            const isPast   = loading && activeLayerIdx > idx;
            const isBlock  = status && ['BLOCK','MISALIGNED','EMERGENCY_BLOCK','DELEGATION_VIOLATION'].includes(status);

            return (
              <div
                key={layer.id}
                className={`p-4 rounded-xl border transition-all duration-300 shadow-sm ${
                  isActive
                    ? 'border-primary bg-primary/10 shadow-[0_0_16px_rgba(var(--primary-rgb),0.25)] scale-[1.01]'
                    : isBlock
                      ? 'border-red-400/60 bg-red-500/10'
                      : status
                        ? 'border-green-400/40 bg-green-500/5'
                        : isPast
                          ? 'border-green-400/40 bg-green-500/5'
                          : 'border-border bg-card'
                }`}
              >
                <div className="flex justify-between items-center">
                  <div className="flex flex-col flex-1 min-w-0 pr-4">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1 font-mono">
                      Layer {layer.id}
                    </span>
                    <h3 className={`font-semibold text-sm mb-0.5 truncate transition-colors ${
                      isActive ? 'text-primary' : 'text-foreground'
                    }`}>
                      {layer.name}
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">{layer.desc}</p>
                  </div>
                  <div className="pl-3 shrink-0">
                    {isActive ? (
                      <Loader2 size={18} className="text-primary animate-spin" />
                    ) : isPast && !status ? (
                      <StatusBadge status="PASS" />
                    ) : status ? (
                      <StatusBadge status={status} />
                    ) : (
                      <span className="text-muted-foreground text-xs font-mono">—</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );

  const account   = portfolio?.account   || {};
  const positions = portfolio?.positions || [];

  const renderPortfolio = (widthClass) => (
    <section className={`bg-card rounded-xl border border-border flex flex-col overflow-hidden shadow-sm shrink-0 h-full w-full ${widthClass}`}>
      <header className="p-6 border-b border-border bg-muted flex items-center justify-between shrink-0">
        <h2 className="text-xl font-semibold text-foreground text-center flex-1">Portfolio Context</h2>
        <button
          onClick={fetchPortfolio}
          disabled={portfolioLoading}
          className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors disabled:opacity-40"
          title="Refresh from Alpaca"
        >
          <RefreshCw size={16} className={portfolioLoading ? 'animate-spin' : ''} />
        </button>
      </header>

      <div className="flex-1 px-6 py-8 overflow-y-auto space-y-6 custom-scrollbar bg-card">

        {account.error && (
          <div className="bg-red-500/10 border border-red-400/40 rounded-xl p-4 text-xs text-red-400 break-all">
            <span className="font-bold">Alpaca Error:</span> {account.error}
          </div>
        )}

        <div className="bg-secondary p-6 rounded-xl border border-border text-center shadow-sm">
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2 font-mono">Total Balance</p>
          <p className="text-3xl lg:text-4xl font-bold text-foreground tracking-tight">
            {account.portfolio_value != null
              ? fmt(account.portfolio_value)
              : <span className="text-muted-foreground text-2xl">{portfolio ? '—' : 'Loading…'}</span>}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-secondary p-5 rounded-xl border border-border text-center shadow-sm">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1.5 font-mono">Available Cash</p>
            <p className="text-xl font-semibold text-foreground">{fmt(account.cash)}</p>
          </div>
          <div className="bg-secondary p-5 rounded-xl border border-border text-center shadow-sm">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1.5 font-mono">Buying Power</p>
            <p className="text-xl font-semibold text-foreground">{fmt(account.buying_power)}</p>
          </div>
        </div>

        <div className="pt-2">
          <h3 className="text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider text-center">Active Positions</h3>
          <div className="border border-border rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted border-b border-border">
                <tr>
                  <th className="px-4 py-3 font-semibold text-muted-foreground text-xs">Asset</th>
                  <th className="px-4 py-3 font-semibold text-muted-foreground text-right text-xs">Qty</th>
                  <th className="px-4 py-3 font-semibold text-muted-foreground text-right text-xs">Value</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-card">
                {positions.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-muted-foreground text-xs">
                      {portfolio ? (account.error ? 'Unavailable' : 'No open positions') : 'Loading…'}
                    </td>
                  </tr>
                )}
                {positions.filter(p => !p.error).map((pos, i) => (
                  <tr key={i} className="hover:bg-secondary">
                    <td className="px-4 py-4 font-semibold text-primary">{pos.symbol}</td>
                    <td className="px-4 py-4 text-right text-muted-foreground text-xs">{pos.qty}</td>
                    <td className="px-4 py-4 text-right text-foreground font-semibold">{fmt(pos.market_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );

  // ── Layout ───────────────────────────────────────────────────────────────────
  return (
    <div className="bg-background text-foreground min-h-screen flex flex-col font-sans overflow-hidden">
      <Navbar onMenuClick={() => setDrawerOpen(true)} />

      {drawerOpen && (
        <div className="fixed inset-0 bg-black/60 z-[60]" onClick={() => setDrawerOpen(false)} />
      )}

      <aside className={`fixed top-0 left-0 h-full w-72 bg-card border-r border-border z-[70] transform transition-transform duration-300 shadow-2xl flex flex-col ${drawerOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 border-b border-border flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center cursor-pointer" onClick={() => navigateTo('Dashboard')}>
              <span className="text-primary-foreground font-bold text-lg leading-none">E</span>
            </div>
            <span className="font-bold tracking-tight text-foreground">ENFORX Navigation</span>
          </div>
          <button onClick={() => setDrawerOpen(false)} className="p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground rounded-lg">
            <X size={20} strokeWidth={2.5} />
          </button>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1">
          <div className="px-5 mb-2">
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Monitoring</span>
          </div>
          <button onClick={() => navigateTo('Chat')}      className={drawerCls('Chat')}>      <MessageSquare  size={18} /> Chat </button>
          <button onClick={() => navigateTo('Pipeline')}  className={drawerCls('Pipeline')}>  <LayoutDashboard size={18} /> Pipeline </button>
          <button onClick={() => navigateTo('Portfolio')} className={drawerCls('Portfolio')}> <Briefcase       size={18} /> Portfolio </button>
          <div className="px-5 mt-8 mb-2">
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">System</span>
          </div>
          <button onClick={() => navigateTo('Configuration')} className={drawerCls('Configuration')}> <Settings2 size={18} /> Configuration </button>
        </nav>
      </aside>

      <main className="flex-1 flex overflow-hidden">
        {activeView === 'Configuration' && (
          <div className="w-full h-full flex flex-col items-center p-12 overflow-y-auto bg-background">
            <div className="w-full max-w-4xl bg-card border border-border rounded-xl p-10 mt-10 shadow-sm min-h-[500px]">
              <h2 className="text-2xl font-bold text-foreground">Configuration</h2>
              <p className="text-sm text-muted-foreground mt-2">Setup and customization</p>
              <div className="mt-12 flex flex-col items-center justify-center h-64 border-2 border-dashed border-border rounded-xl bg-muted">
                <span className="text-muted-foreground text-sm">No configurations loaded.</span>
              </div>
            </div>
          </div>
        )}

        {activeView === 'Dashboard' && (
          <div className="w-full h-full flex flex-col lg:flex-row gap-6 p-6 lg:p-8 lg:overflow-hidden max-w-screen-2xl mx-auto">
            {renderChat('lg:w-[40%]')}
            {renderPipeline('lg:w-[35%]')}
            {renderPortfolio('lg:w-[25%]')}
          </div>
        )}

        {activeView === 'Chat' && (
          <div className="w-full h-full flex p-6 lg:p-8 justify-center overflow-hidden">
            {renderChat('lg:w-[60%] xl:w-[50%]')}
          </div>
        )}

        {activeView === 'Pipeline' && (
          <div className="w-full h-full flex p-6 lg:p-8 justify-center overflow-hidden">
            {renderPipeline('lg:w-[60%] xl:w-[50%]')}
          </div>
        )}

        {activeView === 'Portfolio' && (
          <div className="w-full h-full flex p-6 lg:p-8 justify-center overflow-hidden">
            {renderPortfolio('lg:w-[60%] xl:w-[50%]')}
          </div>
        )}
      </main>

      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 0; background: transparent; }
      `}</style>
    </div>
  );
}
