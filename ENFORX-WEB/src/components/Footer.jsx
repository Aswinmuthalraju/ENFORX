import React from 'react';
import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="w-full border-t border-border bg-card font-sans text-xs mt-auto py-6 transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-4">
        <span className="text-muted-foreground font-medium uppercase tracking-wider">© 2026 ENFORX SECURE. SYSTEM VERSION 4.2.1</span>
        <div className="flex gap-6">
          <Link className="text-muted-foreground hover:text-primary font-medium transition-colors" to="#">Security Policy</Link>
          <Link className="text-muted-foreground hover:text-primary font-medium transition-colors" to="#">Terms</Link>
          <Link className="text-muted-foreground hover:text-primary font-medium transition-colors" to="#">Support</Link>
        </div>
      </div>
    </footer>
  );
}
