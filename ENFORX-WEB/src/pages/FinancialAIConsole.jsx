import React, { useState, useEffect, useRef, useCallback } from 'react';
import Navbar from '../components/Navbar';
import { Send, X, MessageSquare, LayoutDashboard, Briefcase, Settings2, Loader2, ChevronRight } from 'lucide-react';

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    PASS:                 'bg-green-100 text-green-700 border-green-200',
    ALLOW:                'bg-green-100 text-green-700 border-green-200',
    ALIGNED:              'bg-green-100 text-green-700 border-green-200',
    PROCEED:              'bg-green-100 text-green-700 border-green-200',
    AUTHORIZED:           'bg-green-100 text-green-700 border-green-200',
    EXECUTE:              'bg-green-100 text-green-700 border-green-200',
    BLOCK:                'bg-red-100 text-red-700 border-red-300',
    MISALIGNED:           'bg-red-100 text-red-700 border-red-300',
    EMERGENCY_BLOCK:      'bg-red-100 text-red-700 border-red-300',
    DELEGATION_VIOLATION: 'bg-red-100 text-red-700 border-red-300',
    FLAG:                 'bg-yellow-100 text-yellow-700 border-yellow-300',
    CORRECT:              'bg-amber-100 text-amber-700 border-amber-300',
    BUILT:                'bg-blue-100 text-blue-700 border-blue-200',
  };
  const cls = map[status] || 'bg-gray-100 text-gray-600 border-gray-200';
  return (
    <span className={`px-2 py-1 text-xs font-bold rounded border ${cls}`}>
      {status || '—'}
    </span>
  );
}

// ── Layer definitions (static) ────────────────────────────────────────────────

const LAYER_FULL_NAMES = {
  l1_firewall:      'Layer 1 — EnforxGuard Input Firewall',
  l2_ife:           'Layer 2 — Intent Formalization Engine',
  l3_grc:           'Layer 3 — Guided Reasoning Constraints',
  l4_deliberation:  'Layer 4 — Agent Core (Multi-Agent)',
  l5_piav:          'Layer 5 — Plan-Intent Alignment Validator',
  l6_ccv:           'Layer 6 — Causal Chain Validator',
  l7_fdee:          'Layer 7 — FDEE (Safety Controller)',
  l8_dap:           'Layer 8 — Delegation Authority Protocol',
  l9_output:        'Layer 9 — EnforxGuard Output Firewall',
  l10_audit:        'Layer 10 — Adaptive Audit Loop',
  audit:            'Layer 10 — Adaptive Audit Loop',
};

const LAYER_DEFS = [
  { id: 1,  key: 'l1_firewall',     name: 'Input Firewall',   desc: 'Sanitize incoming prompt structures' },
  { id: 2,  key: 'l2_ife',         name: 'Intent Engine',     desc: 'Parse user intent to formal logic' },
  { id: 3,  key: 'l3_grc',         name: 'GRC',               desc: 'Governance, Risk & Compliance bounds check' },
  { id: 4,  key: 'l4_deliberation',name: 'Agent Core',        desc: 'Multi-agent deliberation' },
  { id: 5,  key: 'l5_piav',        name: 'PIAV',              desc: 'Plan-Intent Alignment Validation' },
  { id: 6,  key: 'l6_ccv',         name: 'CCV',               desc: 'Causal Chain Validation' },
  { id: 7,  key: 'l7_fdee',        name: 'FDEE',              desc: 'Financial Domain Enforcement Engine' },
  { id: 8,  key: 'l8_dap',         name: 'DAP',               desc: 'Delegation Authority Protocol' },
  { id: 9,  key: 'l9_output',      name: 'Output Firewall',   desc: 'Secure Alpaca Execution dispatch' },
  { id: 10, key: 'l10_audit',      name: 'Audit Loop',        desc: 'Immutable state capture' },
];

function getLayerStatus(key, pipelineResult) {
  if (!pipelineResult) return null;
  const lr = pipelineResult.layer_results || {};

  // l10 may appear as 'l10_audit' or legacy 'audit' key
  if (key === 'l10_audit') {
    const layer = lr['l10_audit'] || lr['audit'];
    if (layer) return layer.status || layer.result || null;
    return pipelineResult.audit_entry_id ? 'PASS' : null;
  }
  const layer = lr[key];
  if (!layer) return null;
  return layer.status || layer.result || null;
}

function getLayerData(key, pipelineResult) {
  if (!pipelineResult) return null;
  const lr = pipelineResult.layer_results || {};
  if (key === 'l10_audit') {
    return lr['l10_audit'] || lr['audit'] || null;
  }
  return lr[key] || null;
}

// ── Layer detail drawer ───────────────────────────────────────────────────────

function LayerDetailDrawer({ layer, data, onClose }) {
  const drawerRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const title = LAYER_FULL_NAMES[layer?.key] || layer?.name || layer?.key;

  const renderValue = (val) => {
    if (val === null || val === undefined) return <span className="text-gray-400 italic">null</span>;
    if (typeof val === 'boolean') return <span className={val ? 'text-green-600 font-semibold' : 'text-red-500 font-semibold'}>{String(val)}</span>;
    if (typeof val === 'object') {
      return (
        <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap break-words leading-relaxed">
          {JSON.stringify(val, null, 2)}
        </pre>
      );
    }
    return <span className="text-gray-800 font-mono text-xs break-all">{String(val)}</span>;
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-[80] transition-opacity"
        onClick={onClose}
      />
      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed top-0 right-0 h-full w-full max-w-lg bg-white z-[90] shadow-2xl flex flex-col overflow-hidden"
        style={{ animation: 'slideInRight 0.22s ease-out' }}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-200 bg-gray-50 shrink-0">
          <div className="flex-1 pr-4">
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1 font-mono">Layer Detail</p>
            <h2 className="text-base font-bold text-gray-900 leading-snug">{title}</h2>
            {data?.status || data?.result ? (
              <div className="mt-2">
                <StatusBadge status={data.status || data.result} />
              </div>
            ) : null}
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:bg-gray-200 hover:text-gray-900 rounded-lg transition-colors shrink-0"
          >
            <X size={20} strokeWidth={2.5} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
          {!data ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 gap-2">
              <span className="text-sm font-medium">No data yet</span>
              <span className="text-xs">Run a pipeline command to populate this layer.</span>
            </div>
          ) : (
            Object.entries(data).map(([k, v]) => (
              <div key={k} className="border border-gray-100 rounded-lg p-4 bg-white">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 font-mono">{k}</p>
                {renderValue(v)}
              </div>
            ))
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  );
}

// ── Format currency ───────────────────────────────────────────────────────────

function fmt(n) {
  if (n == null || isNaN(n)) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

// ── Main component ────────────────────────────────────────────────────────────

export default function FinancialAIConsole() {
  const [drawerOpen, setDrawerOpen]     = useState(false);
  const [activeView, setActiveView]     = useState('Dashboard');
  const [input, setInput]               = useState('');
  const [messages, setMessages]         = useState([]);
  const [loading, setLoading]           = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [portfolio, setPortfolio]       = useState(null);
  const [selectedLayer, setSelectedLayer] = useState(null); // string key e.g. "l2_ife"
  const chatEndRef = useRef(null);

  const closeLayerDrawer = useCallback(() => setSelectedLayer(null), []);

  // Fetch portfolio on mount
  useEffect(() => {
    fetch('/api/portfolio')
      .then(r => r.json())
      .then(data => setPortfolio(data))
      .catch(err => setPortfolio({ account: { error: err.message }, positions: [] }));
  }, []);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendCommand = async () => {
    const cmd = input.trim();
    if (!cmd || loading) return;

    setMessages(m => [...m, { role: 'user', text: cmd }]);
    setInput('');
    setLoading(true);
    setPipelineResult(null);

    try {
      const res = await fetch('/api/pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await res.json();
      setPipelineResult(data);

      const isBlocked = data.status && data.status !== 'SUCCESS';
      const blockedAt = data.blocked_at || data.status;
      const blockedAtDisplay = LAYER_FULL_NAMES[blockedAt] || blockedAt;
      const execResult = data.execution_result;
      const leaderDec = data.leader_decision;

      let responseText = '';
      if (isBlocked) {
        responseText = `Blocked at ${blockedAtDisplay}.`;
        if (leaderDec?.reasons?.length) {
          responseText += ' ' + leaderDec.reasons.slice(0, 2).join(' ');
        }
      } else if (execResult?.status === 'NO_TRADE') {
        responseText = 'Analysis complete. No trade required for this command.';
      } else if (execResult?.status === 'SUBMITTED' || execResult?.status === 'EXECUTED') {
        responseText = `Trade executed: ${execResult.side?.toUpperCase()} ${execResult.qty} ${execResult.symbol} (Order ${execResult.order_id}).`;
      } else if (execResult?.status === 'ERROR') {
        responseText = `Trade error: ${execResult.error}`;
      } else {
        responseText = `Pipeline completed with status: ${data.status}`;
      }

      setMessages(m => [...m, {
        role: 'enforx',
        text: responseText,
        status: isBlocked ? 'BLOCK' : 'SUCCESS',
      }]);

      // Refresh portfolio after a trade
      if (execResult?.status === 'SUBMITTED') {
        setTimeout(() => {
          fetch('/api/portfolio').then(r => r.json()).then(setPortfolio).catch(() => {});
        }, 2000);
      }
    } catch (err) {
      setMessages(m => [...m, { role: 'enforx', text: 'API error: ' + err.message, status: 'BLOCK' }]);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendCommand(); }
  };

  const navigateTo = (view) => {
    setActiveView(['Chat', 'Pipeline', 'Portfolio'].includes(view) ? 'Dashboard' : view);
    setDrawerOpen(false);
  };

  const getDrawerItemClass = (view) => {
    const isDashboardItem = ['Chat', 'Pipeline', 'Portfolio'].includes(view);
    const isActive = activeView === view || (activeView === 'Dashboard' && isDashboardItem);
    return `flex items-center gap-3 w-full px-5 py-3.5 mt-1 transition-colors cursor-pointer rounded-lg text-sm ${
      isActive ? 'bg-primary/10 text-primary font-bold' : 'text-gray-600 hover:bg-gray-100 font-medium'
    }`;
  };

  // Portfolio values
  const account   = portfolio?.account || {};
  const positions = portfolio?.positions || [];
  const totalValue = account.portfolio_value;
  const cash       = account.cash;

  return (
    <div className="bg-gray-50 text-gray-800 min-h-screen flex flex-col font-sans overflow-hidden">
      <Navbar onMenuClick={() => setDrawerOpen(true)} />

      {drawerOpen && (
        <div className="fixed inset-0 bg-black/50 z-[60]" onClick={() => setDrawerOpen(false)} />
      )}

      <aside className={`fixed top-0 left-0 h-full w-72 bg-white border-r border-gray-200 z-[70] transform transition-transform duration-300 shadow-2xl flex flex-col ${drawerOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 border-b border-gray-200 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg leading-none">E</span>
            </div>
            <span className="font-bold tracking-tight text-gray-900">ENFORX Navigation</span>
          </div>
          <button onClick={() => setDrawerOpen(false)} className="p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 rounded-lg">
            <X size={20} strokeWidth={2.5} />
          </button>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1">
          <div className="px-5 mb-2">
            <span className="text-xs font-bold uppercase tracking-widest text-gray-400">Monitoring</span>
          </div>
          <button onClick={() => navigateTo('Chat')} className={getDrawerItemClass('Chat')}>
            <MessageSquare size={18} /> Chat
          </button>
          <button onClick={() => navigateTo('Pipeline')} className={getDrawerItemClass('Pipeline')}>
            <LayoutDashboard size={18} /> Pipeline
          </button>
          <button onClick={() => navigateTo('Portfolio')} className={getDrawerItemClass('Portfolio')}>
            <Briefcase size={18} /> Portfolio
          </button>
          <div className="px-5 mt-8 mb-2">
            <span className="text-xs font-bold uppercase tracking-widest text-gray-400">System</span>
          </div>
          <button onClick={() => navigateTo('Configuration')} className={getDrawerItemClass('Configuration')}>
            <Settings2 size={18} /> Configuration
          </button>
        </nav>
      </aside>

      <main className="flex-1 flex overflow-hidden">
        {activeView === 'Configuration' ? (
          <div className="w-full h-full flex flex-col items-center p-12">
            <div className="w-full max-w-4xl bg-white border border-gray-200 rounded-xl p-10 mt-10 shadow-sm min-h-[500px]">
              <h2 className="text-2xl font-bold text-gray-900">Configuration</h2>
              <p className="text-sm text-gray-500 mt-2 font-medium">Setup and customization</p>
              <div className="mt-12 flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-200 rounded-xl bg-gray-50/50">
                <span className="text-gray-400 font-medium text-sm">No configurations loaded.</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="w-full h-full flex flex-col lg:flex-row gap-6 p-6 lg:p-8 lg:overflow-hidden">

            {/* Panel 1: Chat */}
            <section className="w-full lg:w-[35%] bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden shadow-sm shrink-0 lg:h-full">
              <header className="p-6 border-b border-gray-200 bg-white z-10 shrink-0">
                <h2 className="text-xl font-semibold text-gray-900">Session</h2>
              </header>

              <div className="flex-1 px-6 py-6 overflow-y-auto space-y-6 custom-scrollbar bg-white">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 gap-2">
                    <MessageSquare size={32} strokeWidth={1.5} />
                    <p className="text-sm font-medium">Send a trade command to begin</p>
                    <p className="text-xs">e.g. "Buy 5 shares of AAPL"</p>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <div key={i} className="flex flex-col gap-1.5 items-start">
                    <span className={`text-xs font-bold uppercase tracking-wider ${msg.role === 'user' ? 'text-gray-400' : 'text-primary'}`}>
                      {msg.role === 'user' ? 'User' : 'Enforx Kernel'}
                    </span>
                    {msg.role === 'user' ? (
                      <div className="bg-gray-100 p-4 rounded-xl text-sm text-gray-800 w-full border border-gray-200 leading-relaxed">
                        {msg.text}
                      </div>
                    ) : (
                      <div className="bg-primary p-4 rounded-xl text-sm text-white w-full shadow-md leading-relaxed">
                        {msg.status && (
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${
                              msg.status === 'BLOCK'
                                ? 'bg-red-500/20 border-red-400 text-red-100'
                                : 'bg-green-500/20 border-green-400 text-green-100'
                            }`}>
                              {msg.status}
                            </span>
                          </div>
                        )}
                        <p className="text-slate-100">{msg.text}</p>
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="flex flex-col gap-1.5 items-start">
                    <span className="text-xs font-bold uppercase tracking-wider text-primary">Enforx Kernel</span>
                    <div className="bg-primary p-4 rounded-xl text-sm text-white w-full shadow-md flex items-center gap-2">
                      <Loader2 size={16} className="animate-spin" />
                      <span className="text-slate-200">Running 10-layer pipeline...</span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="p-5 border-t border-gray-200 bg-gray-50 flex gap-3 items-center shrink-0">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={loading}
                  className="flex-1 bg-white border border-gray-300 rounded-lg px-5 py-3 lg:py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent text-gray-900 placeholder-gray-400 disabled:opacity-60"
                  placeholder="Enter command..."
                />
                <button
                  onClick={sendCommand}
                  disabled={loading || !input.trim()}
                  className="px-5 py-3 lg:py-4 bg-primary text-white font-semibold rounded-lg hover:opacity-90 transition-opacity whitespace-nowrap text-sm disabled:opacity-50 flex items-center gap-2"
                >
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  Send
                </button>
              </div>
            </section>

            {/* Panel 2: Pipeline */}
            <section className="w-full lg:w-[40%] bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden shadow-sm shrink-0 lg:h-full relative">
              <header className={`p-6 border-b flex justify-between items-center shrink-0 transition-colors ${
                pipelineResult?.status === 'SUCCESS'
                  ? 'bg-green-50/60 border-green-200'
                  : pipelineResult?.status && pipelineResult.status !== 'SUCCESS'
                    ? 'bg-red-50/60 border-red-200'
                    : 'bg-gray-50/50 border-gray-200'
              }`}>
                <div className="w-full">
                  <h2 className="text-xl font-semibold text-center text-gray-900">Execution Pipeline</h2>
                  <div className="flex justify-center mt-2">
                    {pipelineResult ? (
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                        pipelineResult.status === 'SUCCESS'
                          ? 'bg-green-100 text-green-700 border-green-300'
                          : 'bg-red-100 text-red-700 border-red-300'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${pipelineResult.status === 'SUCCESS' ? 'bg-green-500' : 'bg-red-500'}`} />
                        {pipelineResult.status}
                      </span>
                    ) : (
                      <span className="text-sm text-gray-400 font-medium">Awaiting command</span>
                    )}
                  </div>
                </div>
              </header>

              <div className="flex-1 px-8 py-8 overflow-y-auto w-full relative custom-scrollbar bg-white">
                <div className="max-w-md mx-auto relative flex flex-col space-y-0 pb-8">
                  {(() => {
                    // Find the index of the first blocked layer so we can grey out everything after it
                    const BLOCKED_STATUSES = new Set(['BLOCK', 'MISALIGNED', 'EMERGENCY_BLOCK', 'DELEGATION_VIOLATION']);
                    let blockedLayerIdx = -1;
                    if (pipelineResult && pipelineResult.status !== 'SUCCESS') {
                      for (let i = 0; i < LAYER_DEFS.length; i++) {
                        const st = getLayerStatus(LAYER_DEFS[i].key, pipelineResult);
                        if (st && (BLOCKED_STATUSES.has(st) || st.includes('BLOCK'))) {
                          blockedLayerIdx = i;
                          break;
                        }
                      }
                    }

                    return LAYER_DEFS.map((layer, idx) => {
                      const status    = getLayerStatus(layer.key, pipelineResult);
                      const isBlocked = status && (BLOCKED_STATUSES.has(status) || status.includes('BLOCK'));
                      const isFlagged = status === 'FLAG' || status === 'CORRECT';
                      const isSkipped = blockedLayerIdx >= 0 && idx > blockedLayerIdx;

                      const cardCls = isSkipped
                        ? 'bg-gray-50 border-gray-200 opacity-50 shadow-sm'
                        : isBlocked
                          ? 'bg-red-50 border-red-200 shadow-sm hover:shadow-md hover:border-red-300'
                          : isFlagged
                            ? 'bg-yellow-50 border-yellow-200 shadow-sm hover:shadow-md hover:border-yellow-300'
                            : status
                              ? 'bg-green-50 border-green-200 shadow-sm hover:shadow-md hover:border-green-300'
                              : 'bg-white border-gray-200 shadow-sm hover:shadow-md hover:border-gray-300';

                      return (
                        <React.Fragment key={layer.id}>
                          {idx > 0 && (
                            <div className="flex justify-center">
                              <div className={`h-6 w-[2px] ${isSkipped ? 'bg-gray-100' : 'bg-gray-200'}`} />
                            </div>
                          )}
                          <div
                            onClick={() => setSelectedLayer(layer.key)}
                            className={`p-5 rounded-lg border transition-all cursor-pointer group ${cardCls}`}
                          >
                            <div className="flex justify-between items-center">
                              <div className="flex flex-col">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5 font-mono">Layer {layer.id}</span>
                                <h3 className={`font-semibold text-sm mb-0.5 ${isSkipped ? 'text-gray-400' : 'text-gray-900'}`}>{layer.name}</h3>
                                <p className="text-xs text-gray-400 leading-relaxed pr-2">{layer.desc}</p>
                              </div>
                              <div className="pl-3 shrink-0 flex items-center gap-1.5">
                                {isSkipped
                                  ? <span className="text-gray-300 text-xs font-mono italic">skipped</span>
                                  : status
                                    ? <StatusBadge status={status} />
                                    : loading
                                      ? <Loader2 size={16} className="text-gray-300 animate-spin" />
                                      : <span className="text-gray-300 text-xs font-mono">—</span>
                                }
                                <ChevronRight size={14} className="text-gray-300 group-hover:text-gray-500 transition-colors" />
                              </div>
                            </div>
                          </div>
                        </React.Fragment>
                      );
                    });
                  })()}
                </div>
              </div>
            </section>

            {/* Panel 3: Portfolio */}
            <section className="w-full lg:w-[25%] bg-white rounded-xl border border-gray-200 flex flex-col overflow-hidden shadow-sm shrink-0 lg:h-full">
              <header className="p-6 border-b border-gray-200 bg-gray-50/50 shrink-0">
                <h2 className="text-xl font-semibold text-gray-900 text-center">Portfolio Context</h2>
              </header>

              <div className="flex-1 px-6 py-8 overflow-y-auto space-y-8 custom-scrollbar bg-white">
                <div className="flex flex-col gap-6">
                  {account.error && (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-xs text-red-600 text-center break-all">
                      <span className="font-bold">API Error:</span> {account.error}
                    </div>
                  )}
                  <div className="bg-white p-6 rounded-xl border border-gray-200 text-center shadow-sm">
                    <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-2 font-mono">Total Balance</p>
                    <p className="text-3xl lg:text-4xl font-bold text-gray-900 tracking-tight">
                      {totalValue != null ? fmt(totalValue) : <span className="text-gray-300 text-2xl">{portfolio ? '—' : 'Loading...'}</span>}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 lg:grid-cols-1 xl:grid-cols-2 gap-4">
                    <div className="bg-white p-5 rounded-xl border border-gray-200 text-center shadow-sm">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5 font-mono">Available Cash</p>
                      <p className="text-xl font-semibold text-gray-800">{cash != null ? fmt(cash) : '—'}</p>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-gray-200 text-center shadow-sm">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1.5 font-mono">Buying Power</p>
                      <p className="text-xl font-semibold text-gray-800">{account.buying_power != null ? fmt(account.buying_power) : '—'}</p>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <h3 className="text-xs font-semibold mb-3 text-gray-500 uppercase tracking-wider text-center">Active Positions</h3>
                  <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="px-4 py-3 font-semibold text-gray-600 text-xs">Asset</th>
                          <th className="px-4 py-3 font-semibold text-gray-600 text-right text-xs">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 bg-white">
                        {positions.length === 0 && (
                          <tr>
                            <td colSpan={2} className="px-4 py-6 text-center text-gray-400 text-xs">
                              {portfolio ? 'No open positions' : 'Loading...'}
                            </td>
                          </tr>
                        )}
                        {positions.filter(p => !p.error).map((pos, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-4 py-4 font-semibold text-primary">{pos.symbol}</td>
                            <td className="px-4 py-4 text-right text-gray-900 font-semibold">{fmt(pos.market_value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </section>

          </div>
        )}
      </main>

      {selectedLayer && (
        <LayerDetailDrawer
          layer={LAYER_DEFS.find(l => l.key === selectedLayer) || { key: selectedLayer, name: selectedLayer }}
          data={getLayerData(selectedLayer, pipelineResult)}
          onClose={closeLayerDrawer}
        />
      )}

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 0; background: transparent; }
      `}</style>
    </div>
  );
}
