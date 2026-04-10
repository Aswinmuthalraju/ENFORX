import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bell, Settings, User, Menu, Sun, Moon } from 'lucide-react';

export default function Navbar({ onMenuClick }) {
  const location = useLocation();
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  const getNavClass = (path) => {
    const baseClass = "text-sm transition-colors ";
    const isActive = location.pathname === path;
    
    if (isActive) {
      return baseClass + "font-semibold text-primary border-b-2 border-primary pb-1";
    }
    return baseClass + "font-medium text-muted-foreground hover:text-foreground";
  };

  return (
    <nav className="w-full top-0 sticky z-50 py-4 bg-background border-b border-border flex justify-between items-center h-16 px-6 lg:px-8 max-w-full font-sans antialiased text-foreground">
      <div className="flex items-center gap-6 lg:gap-12">
        <div className="flex items-center gap-4">
          {onMenuClick && (
            <button 
              onClick={onMenuClick}
              className="p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors rounded-lg flex items-center justify-center shrink-0"
            >
              <Menu size={24} strokeWidth={2.5} />
            </button>
          )}
          <div className="text-xl font-bold tracking-tight text-primary">
            <Link to="/">ENFORX</Link>
          </div>
        </div>
        
        <div className="hidden md:flex gap-8 items-center mt-1">
          <Link className={getNavClass("/")} to="/">Home</Link>
          <Link className={getNavClass("/web")} to="/web">Web</Link>
          <Link className={getNavClass("/setup")} to="/setup">PlugIn</Link>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <button 
          onClick={toggleTheme}
          className="p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors rounded-lg"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={20} strokeWidth={2} /> : <Moon size={20} strokeWidth={2} />}
        </button>
        <button className="p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors rounded-lg">
          <Bell size={20} strokeWidth={2} />
        </button>
        <button className="p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors rounded-lg">
          <Settings size={20} strokeWidth={2} />
        </button>
        <div className="h-8 w-8 bg-secondary rounded-full flex items-center justify-center overflow-hidden border border-border text-muted-foreground">
          <User size={16} strokeWidth={2}/>
        </div>
      </div>
    </nav>
  );
}
