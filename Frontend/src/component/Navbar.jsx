import React, { useState, useEffect } from 'react';

export default function JarvisNavbar({ blobSettings, setBlobSettings, currentPage, setCurrentPage, setShowSettingsPopup }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState('');
  const [aiConfidence, setAiConfidence] = useState(98.7);

  // Simulate real-time metrics update
  useEffect(() => {
    const updateMetrics = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      setCurrentTime(timeStr);
      setAiConfidence(prev => {
        const delta = (Math.random() - 0.5) * 0.4;
        return Math.min(99.9, Math.max(97.5, prev + delta));
      });
    };
    updateMetrics();
    const interval = setInterval(updateMetrics, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleNavigation = (item) => {
    if (item === 'Settings') {
      if (setShowSettingsPopup) setShowSettingsPopup(true);
      setMobileMenuOpen(false);
    } else {
      if (setCurrentPage) setCurrentPage(item);
      setMobileMenuOpen(false);
    }
  };

  const navItems = ['Home', 'Dashboard', 'Settings', 'About'];

  return (
    <nav className="fixed top-4 left-4 right-4 z-50 bg-black/40 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl shadow-cyan-500/10 transition-all duration-500 pointer-events-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex items-center justify-between flex-wrap gap-3">

          {/* LEFT SIDE: LOGO + STATUS RING */}
          <div className="flex items-center space-x-3 cursor-pointer group relative" onClick={() => handleNavigation('Home')}>
            <div className="relative w-11 h-11 flex items-center justify-center">
              <div className="absolute inset-0 border border-cyan-500/40 rounded-full animate-ping opacity-30 [animation-duration:2s]"></div>
              <div className="absolute inset-0 border-2 border-cyan-500/50 rounded-full border-t-cyan-300 border-r-purple-500/30 animate-spin [animation-duration:4s]"></div>
              <div className="absolute inset-1 border border-white/20 rounded-full"></div>
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600 flex items-center justify-center shadow-[0_0_25px_rgba(6,182,212,0.7)] group-hover:scale-110 transition-all duration-300">
                <svg className="w-4 h-4 text-white drop-shadow-md" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM8 16a2 2 0 104 0H8z" />
                </svg>
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline space-x-1">
                <span className="text-white font-extrabold text-xl tracking-[0.15em] uppercase leading-none bg-gradient-to-r from-white to-cyan-300 bg-clip-text text-transparent">
                  BRAHMASTRA
                </span>
                <span className="text-cyan-400 font-black text-xl tracking-tight">AI</span>
              </div>
              <div className="flex items-center space-x-2 mt-0.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#2ecc71]"></div>
                <span className="text-[9px] font-mono font-bold text-cyan-300/90 tracking-[0.25em] uppercase">
                  SYSTEM STATUS: ACTIVE
                </span>
              </div>
            </div>
          </div>

          {/* CENTER: HUD NAVIGATION - DESKTOP */}
          <div className="hidden md:flex items-center bg-white/5 backdrop-blur-lg border border-white/15 px-6 py-2 rounded-full space-x-8 relative overflow-hidden group shadow-inner shadow-white/5">
            <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-out"></div>

            {navItems.map((item, idx) => (
              <div key={idx} className="relative group/navitem">
                <button
                  onClick={() => handleNavigation(item)}
                  className={`relative hover:text-cyan-300 text-[11px] font-bold tracking-[0.12em] uppercase transition-all duration-300 flex items-center group/link py-1 ${currentPage === item ? 'text-cyan-400' : 'text-gray-300'}`}
                >
                  <span className={`absolute -bottom-0 left-0 h-[2px] bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-300 ${currentPage === item ? 'w-full' : 'w-0 group-hover/link:w-full'}`}></span>
                  <span className={`w-1 h-1 rounded-full bg-cyan-400 mr-2 transition-opacity shadow-md ${currentPage === item ? 'opacity-100' : 'opacity-0 group-hover/link:opacity-100'}`}></span>
                  {item}
                </button>
              </div>
            ))}
          </div>

          {/* RIGHT SIDE: METRICS + AUTH BUTTON */}
          <div className="flex items-center gap-5">
            <div className="hidden lg:flex items-center gap-3 bg-black/30 rounded-xl px-3 py-1.5 border border-white/10 backdrop-blur-sm font-mono text-[9px]">
              <div className="flex flex-col items-end">
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">LATENCY</span>
                  <span className="text-emerald-300 font-bold">12.4ms</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">NET_RNG</span>
                  <span className="text-cyan-300 font-bold">ACTIVE</span>
                </div>
              </div>
              <div className="w-px h-6 bg-white/20"></div>
              <div className="flex flex-col">
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">AI CONF.</span>
                  <span className="text-purple-300 font-bold">{aiConfidence.toFixed(1)}%</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-slate-400">SECURE</span>
                  <span className="text-emerald-300 font-bold">TRUE</span>
                </div>
              </div>
            </div>

            <button className="relative group overflow-hidden px-5 py-2 bg-gradient-to-r from-cyan-950/80 to-blue-950/80 text-cyan-300 border border-cyan-500/60 rounded-md transition-all duration-500 hover:shadow-[0_0_18px_#06b6d4] hover:border-cyan-400 flex items-center gap-2">
              <span className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"></span>
              <svg className="w-3.5 h-3.5 text-cyan-400 group-hover:animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <span className="text-[11px] font-bold tracking-[0.15em] uppercase relative z-10">
                Initialize_Access
              </span>
            </button>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-cyan-300 bg-white/5 p-2 rounded-lg border border-white/10 hover:bg-white/10 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Bottom glowing accent line */}
      <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-60"></div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden absolute top-full left-4 right-4 mt-2 bg-black/90 backdrop-blur-2xl border border-white/10 rounded-xl p-4 flex flex-col gap-2 shadow-[0_0_30px_rgba(6,182,212,0.2)] z-50">
          {navItems.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleNavigation(item)}
              className={`text-left px-4 py-3 rounded-lg text-xs font-bold tracking-[0.15em] uppercase transition-colors ${currentPage === item ? 'bg-cyan-500/20 text-cyan-400' : 'text-gray-300 hover:bg-white/10'}`}
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </nav>
  );
}