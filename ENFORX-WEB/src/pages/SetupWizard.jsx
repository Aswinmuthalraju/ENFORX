import React, { useState } from 'react';
import Navbar from '../components/Navbar';
import { Copy, Check } from 'lucide-react';

function CodeBlock({ code }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group mt-3 mb-5">
      <div className="absolute right-2 top-2">
        <button 
          onClick={handleCopy}
          className="p-1.5 bg-secondary hover:bg-accent text-muted-foreground rounded border border-border transition-colors text-xs font-semibold flex items-center gap-1.5"
          aria-label="Copy to clipboard"
        >
          {copied ? (
             <><Check size={14} className="text-green-500"/> Copied</>
          ) : (
             <><Copy size={14} /> Copy</>
          )}
        </button>
      </div>
      <pre className="bg-muted text-foreground p-4 rounded-lg overflow-x-auto border border-border text-sm font-mono leading-relaxed pt-11 md:pt-4 pr-20">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function SetupWizard() {
  const [openStep, setOpenStep] = useState(1);

  const steps = [
    {
      id: 1,
      title: "Download ENFORX",
      content: (
        <div className="space-y-4 text-muted-foreground pt-2 pb-1">
          <p className="text-sm">Download the ENFORX project as a ZIP file or clone the repository.</p>
          <CodeBlock code={`git clone <repo-url>\ncd ENFORX`} />
        </div>
      )
    },
    {
      id: 2,
      title: "Prerequisites",
      content: (
        <div className="space-y-4 pt-2 pb-1">
          <ul className="list-disc list-outside ml-5 space-y-2.5 text-sm text-foreground opacity-90">
            <li>OpenClaw CLI + Gateway (must be running)</li>
            <li>Node.js ≥ 22</li>
            <li>Python 3.10+</li>
            <li>ENFORX dependencies (requirements.txt)</li>
            <li>.env configuration (API keys required)</li>
            <li>enforx-policy.json must be present</li>
          </ul>
        </div>
      )
    },
    {
      id: 3,
      title: "Setup Instructions",
      content: (
        <div className="space-y-8 pt-4 pb-2">
          
          <div>
            <h4 className="text-sm font-semibold text-foreground mb-1">1. Create Python Environment</h4>
            <CodeBlock code={`python -m venv venv\nsource venv/bin/activate\n# OR\nvenv\\Scripts\\activate`} />
          </div>

          <div>
            <h4 className="text-sm font-semibold text-foreground mb-1">2. Install Dependencies</h4>
            <CodeBlock code={`pip install -r requirements.txt`} />
          </div>

          <div>
            <h4 className="text-sm font-semibold text-foreground mb-1">3. Configure Environment</h4>
            <CodeBlock code={`cp .env.example .env`} />
            <ul className="list-disc list-outside ml-5 space-y-2 mt-3 text-sm text-muted-foreground">
              <li>Set OpenClaw API</li>
              <li>Set Trading API (Alpaca)</li>
              <li>Add required credentials</li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-foreground mb-1">4. Verify System</h4>
            <CodeBlock code={`python -m src.cli --health`} />
            <div className="bg-secondary border border-border text-foreground px-4 py-3 rounded-lg text-sm font-medium mt-3">
              This must succeed before proceeding.
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-foreground mb-1">5. Install Plugin</h4>
            <CodeBlock code={`openclaw plugins install --link ./plugin`} />
            <p className="text-sm text-muted-foreground font-medium mt-3">Restart OpenClaw gateway</p>
          </div>

        </div>
      )
    }
  ];

  return (
    <div className="bg-background text-foreground min-h-screen flex flex-col font-sans transition-colors duration-200">
      <Navbar />

      <main className="flex-1 flex justify-center p-6 lg:p-12 w-full">
        <div className="w-full max-w-[800px] flex flex-col">
          
          <div className="mb-10 text-center md:text-left">
            <h1 className="text-3xl font-bold tracking-tight text-foreground mb-3">PlugIn Setup Guide</h1>
            <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
              Official developer instructions for configuring and linking the ENFORX kernel to your operational environment.
            </p>
          </div>

          <div className="space-y-4">
            {steps.map((step) => {
              const isActive = openStep === step.id;

              return (
                <div 
                  key={step.id} 
                  className={`border rounded-xl transition-colors duration-200 overflow-hidden ${
                    isActive ? 'border-primary bg-accent shadow-sm' : 'border-border bg-card hover:border-accent'
                  }`}
                >
                  <button 
                    onClick={() => setOpenStep(step.id)}
                    className="w-full px-6 py-5 flex items-center justify-between focus:outline-none text-left"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-8 h-8 rounded flex justify-center items-center font-bold text-sm transition-colors ${
                        isActive ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground'
                      }`}>
                        {step.id}
                      </div>
                      <h3 className={`font-semibold text-lg ${isActive ? 'text-primary' : 'text-foreground opacity-90'}`}>
                        {step.title}
                      </h3>
                    </div>
                  </button>
                  
                  {isActive && (
                    <div className="px-6 pb-6 pt-2 lg:pl-[70px] animate-in slide-in-from-top-2 fade-in duration-200">
                      {step.content}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

        </div>
      </main>
    </div>
  );
}
