import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import Footer from '../components/Footer';
import { Link } from 'react-router-dom';
import { Shield, GitBranch, Terminal, History } from 'lucide-react';

export default function LandingPage() {
  const [hoveredLayer, setHoveredLayer] = useState(null);

  return (
    <div className="bg-background text-foreground antialiased font-sans flex flex-col min-h-screen transition-colors duration-200">
      <Navbar />
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 lg:px-8">
        
        {/* Hero Section */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-16 py-20 items-center">
          <div className="space-y-8">
            <h1 className="text-4xl md:text-5xl font-semibold tracking-tight leading-tight text-foreground">
              Causal Integrity Enforcement for Autonomous AI Agents
            </h1>
            <p className="text-sm md:text-base text-muted-foreground max-w-xl leading-relaxed">
              Deterministic validation for AI reasoning chains. Secure, verifiable, and precision-engineered for the next generation of autonomous intelligence.
            </p>
            <div className="flex items-center gap-4 pt-4">
              <Link to="/web" className="bg-primary text-primary-foreground px-5 py-2.5 rounded-lg font-semibold text-sm hover:opacity-90 transition-opacity">
                Open Web
              </Link>
              <button className="px-5 py-2.5 rounded-lg border border-border font-semibold text-sm text-foreground hover:bg-secondary transition-colors">
                View Docs
              </button>
            </div>
          </div>
          
          <div className="relative flex justify-center items-center py-4">
            <div className="flex flex-col items-center" style={{ perspective: '800px', overflow: 'visible' }}>
              {[
                { id: 1,  name: "EnforxGuard Input Firewall",          color: "bg-green-500" },
                { id: 2,  name: "Intent Formalization Engine",          color: "bg-green-500" },
                { id: 3,  name: "Guided Reasoning Constraints",         color: "bg-orange-400", active: true },
                { id: 4,  name: "Agent Core",                           color: "bg-background", isPrimary: true },
                { id: 5,  name: "Plan-Intent Alignment Validator",      color: "bg-green-500" },
                { id: 6,  name: "Causal Chain Validator",               color: "bg-green-500" },
                { id: 7,  name: "FDEE (Safety Controller)",             color: "bg-purple-500" },
                { id: 8,  name: "Delegation Authority Protocol",        color: "bg-green-500" },
                { id: 9,  name: "EnforxGuard Output Firewall",         color: "bg-green-500" },
                { id: 10, name: "Adaptive Audit Loop",                  color: "bg-green-500" },
              ].map((layer, idx) => {
                const isHovered = hoveredLayer === layer.id;
                return (
                  <div
                    key={layer.id}
                    onMouseEnter={() => setHoveredLayer(layer.id)}
                    onMouseLeave={() => setHoveredLayer(null)}
                    style={{
                      zIndex: isHovered ? 999 : (20 - idx),
                      marginTop: idx === 0 ? '0px' : '-26px',
                      transform: isHovered
                        ? 'rotateX(0deg) scale(1.12) translateY(-10px)'
                        : 'rotateX(-8deg) scale(1)',
                      transition: 'all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                    }}
                    className={`w-72 lg:w-80 h-12 ${
                      layer.isPrimary
                        ? isHovered
                          ? 'bg-primary border-primary shadow-2xl'
                          : 'bg-primary border-primary shadow-xl'
                        : isHovered
                        ? 'bg-card border-primary shadow-2xl'
                        : 'bg-card border-border shadow-md'
                    } border rounded-xl flex items-center px-4 gap-3 cursor-pointer`}
                  >
                    <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${layer.color} ${layer.isPrimary ? 'animate-pulse' : ''}`}></div>
                    <span className={`text-[10px] font-bold uppercase tracking-widest ${
                      isHovered ? 'whitespace-nowrap' : 'truncate'
                    } ${
                      layer.isPrimary
                        ? 'text-primary-foreground'
                        : layer.active
                        ? isHovered ? 'text-orange-400' : 'text-orange-500'
                        : isHovered
                        ? 'text-primary'
                        : 'text-muted-foreground'
                    } transition-colors duration-200`}>
                      L{layer.id}: {layer.name}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Core Idea Comparison */}
        <section className="py-20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="p-8 bg-card border border-border rounded-lg shadow-sm">
              <h3 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase mb-6">Traditional AI Agents</h3>
              <div className="space-y-6">
                <div>
                  <h4 className="font-semibold text-lg mb-2 text-foreground">Reactive Validation</h4>
                  <p className="text-muted-foreground text-sm leading-relaxed">Safety checks occur after reasoning, leading to latency and potential security escapes.</p>
                </div>
                <div className="opacity-75">
                  <h4 className="font-semibold text-lg mb-2 text-foreground">Probabilistic Logic</h4>
                  <p className="text-muted-foreground text-sm leading-relaxed">Agent outcomes are variable, making regulatory compliance nearly impossible to guarantee.</p>
                </div>
              </div>
            </div>
            
            <div className="p-8 bg-secondary text-secondary-foreground rounded-lg shadow-md border border-border">
              <h3 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase mb-6">ENFORX Protocol</h3>
              <div className="space-y-6">
                <div>
                  <h4 className="font-semibold text-lg mb-2 text-secondary-foreground">Proactive Enforcement</h4>
                  <p className="text-secondary-foreground opacity-80 text-sm leading-relaxed">Constraints are baked into the causal chain, ensuring every token aligns with security policies.</p>
                </div>
                <div>
                  <h4 className="font-semibold text-lg mb-2 text-secondary-foreground">Deterministic Chains</h4>
                  <p className="text-secondary-foreground opacity-80 text-sm leading-relaxed">Mathematically provable validation stages that eliminate reasoning drift and hallucinations.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 10-Layer Pipeline Detail Summary */}
        <section className="py-20">
          <div className="mb-12">
            <h2 className="text-3xl font-semibold tracking-tight text-foreground mb-4">The Fortified Pipeline</h2>
            <p className="text-muted-foreground max-w-2xl text-sm leading-relaxed">A modular, ten-stage architecture that ensures total causal integrity for enterprise AI deployments.</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-6">
            
            {[
              { id: 1, name: "Input Firewall", status: "PASS", variant: "default" },
              { id: 2, name: "Intent Engine", status: "PASS", variant: "default" },
              { id: 3, name: "GRC Hub", status: "FLAG", variant: "default" },
              { id: 4, name: "Agent Core", status: "ACTIVE", variant: "primary" },
              { id: 5, name: "PIAV Engine", status: "PASS", variant: "default" },
              { id: 6, name: "CCV Check", status: "PASS", variant: "default" },
              { id: 7, name: "FDEE Logic", status: "CORRECT", variant: "default" },
              { id: 8, name: "DAP Monitor", status: "PASS", variant: "default" },
              { id: 9, name: "Output Firewall", status: "PASS", variant: "default" },
              { id: 10, name: "Audit Loop", status: "PASS", variant: "default" },
            ].map((layer) => (
              <div key={layer.id} className={`${layer.variant === 'primary' ? 'bg-primary text-primary-foreground border-primary' : 'bg-card text-foreground border-border'} p-5 border rounded-lg flex flex-col justify-between min-h-[140px] shadow-sm`}>
                <div className={`text-xs font-semibold tracking-wider uppercase ${layer.variant === 'primary' ? 'text-primary-foreground opacity-70' : 'text-muted-foreground'}`}>
                  Layer {layer.id < 10 ? `0${layer.id}` : layer.id}
                </div>
                <div>
                  <h5 className="font-semibold text-sm mb-1">{layer.name}</h5>
                  <p className={`text-xs font-medium uppercase tracking-wider ${
                    layer.status === 'PASS' ? 'text-green-600' :
                    layer.status === 'FLAG' ? 'text-orange-500' :
                    layer.status === 'CORRECT' ? 'text-purple-600' :
                    layer.status === 'BLOCK' ? 'text-red-600' : 'text-muted-foreground'
                  }`}>
                    {layer.status}
                  </p>
                </div>
              </div>
            ))}
            
          </div>
        </section>

        {/* Key Features Grid */}
        <section className="py-20 border-t border-border">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="bg-card p-6 border border-border rounded-lg flex flex-col gap-4 shadow-sm">
              <Shield className="text-primary" size={24} />
              <h6 className="font-semibold text-sm text-foreground">Dual Firewalls</h6>
              <p className="text-sm text-muted-foreground leading-relaxed">Pre-processing and post-generation shields that filter adversarial prompts and prevent data leakage with zero overhead.</p>
            </div>
            <div className="bg-card p-6 border border-border rounded-lg flex flex-col gap-4 shadow-sm">
              <GitBranch className="text-primary" size={24} />
              <h6 className="font-semibold text-sm text-foreground">Guided Reasoning</h6>
              <p className="text-sm text-muted-foreground leading-relaxed">Constrain the AI’s internal logic using structured GRC templates.</p>
            </div>
            <div className="bg-card p-6 border border-border rounded-lg flex flex-col gap-4 shadow-sm">
              <Terminal className="text-primary" size={24} />
              <h6 className="font-semibold text-sm text-foreground">Deterministic Logic</h6>
              <p className="text-sm text-muted-foreground leading-relaxed">Replace prompt-based expectation with code-driven enforcement. If it doesn't pass the check, it doesn't run.</p>
            </div>
            <div className="bg-card p-6 border border-border rounded-lg flex flex-col gap-4 shadow-sm">
              <History className="text-primary" size={24} />
              <h6 className="font-semibold text-sm text-foreground">Adaptive Audit</h6>
              <p className="text-sm text-muted-foreground leading-relaxed">Real-time recording of every causal step, allowing for instantaneous post-mortem analysis and refinement.</p>
            </div>
          </div>
        </section>
        
      </main>
      <Footer />
    </div>
  );
}
