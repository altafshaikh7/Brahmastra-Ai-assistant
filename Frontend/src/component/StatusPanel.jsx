import React, { useEffect, useState } from "react";

const StatusPanel = ({ systemState }) => {
  const [time, setTime] = useState(new Date());
  const {
    micStatus,
    apiStatus,
    aiStatus,
    authStatus,
    systemStatus,
    isSpeaking,
    isProcessing,
    volume = 0
  } = systemState;

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const statuses = [
    { label: "AI CORE", value: aiStatus, active: aiStatus === 'ONLINE' },
    { label: "MICROPHONE", value: micStatus, active: micStatus === 'ACTIVE' },
    { label: "AUTHORIZATION", value: authStatus, active: authStatus === 'GRANTED' },
    { label: "API UPLINK", value: apiStatus, active: apiStatus === 'CONNECTED' },
    { label: "SYSTEM", value: systemStatus, active: systemStatus === 'NOMINAL' },
  ];

  return (
    <div className="fixed top-20 right-2 z-50 flex flex-col gap-4 md:gap-6 pointer-events-none md:right-8 lg:right-12 sm:top-24 max-w-[280px] sm:max-w-xs md:max-w-md">
      {/* HUD Header */}
      <div className="flex flex-col items-end">
        <div className="flex items-center gap-2 md:gap-3 justify-end">
          <span className="text-[8px] md:text-[10px] text-cyan-400 font-mono tracking-[4px] md:tracking-[6px] uppercase font-bold text-right whitespace-nowrap">
            System Monitoring
          </span>
          <div className="w-6 md:w-10 h-[2px] bg-cyan-500 shadow-[0_0_10px_#06b6d4]" />
        </div>
        <div className="text-[20px] md:text-[32px] font-black text-white/90 font-mono tracking-tighter -mt-1 flex items-baseline gap-2 justify-end">
          <span className="text-cyan-500 text-[8px] md:text-xs animate-pulse font-normal">SYNC_ON</span>
          <span className="whitespace-nowrap">{time.toLocaleTimeString([], { hour12: false })}</span>
        </div>
      </div>

      {/* Real-time Visualizer */}
      <div className="flex flex-col gap-1 md:gap-2 items-end">
        <span className="text-[7px] md:text-[8px] text-white/30 font-mono tracking-[2px] md:tracking-[4px] uppercase text-right">Neural Signal Analysis</span>
        <div className="flex items-end gap-[2px] md:gap-1 h-8 md:h-12 justify-end">
          {[...Array(10)].map((_, i) => {
            const h = Math.max(4, (volume * (Math.random() * 0.5 + 0.5)) * (1.5 - Math.abs(i - 5) / 5));
            return (
              <div
                key={i}
                className={`w-1 transition-all duration-75 rounded-t-sm ${isSpeaking ? 'bg-purple-500 shadow-[0_0_8px_#a855f7]' : 'bg-cyan-500 shadow-[0_0_8px_#06b6d4]'}`}
                style={{ height: `${h}%`, opacity: 0.3 + (h / 100) }}
              />
            );
          })}
        </div>
      </div>

      {/* Status Indicators */}
      <div className="flex flex-col gap-2 md:gap-4 items-end">
        {statuses.map((s, i) => (
          <div
            key={i}
            className="flex flex-col gap-0 md:gap-1 group animate-in slide-in-from-right duration-500"
            style={{ animationDelay: `${i * 100}ms` }}
          >
            <div className="flex items-center gap-2 md:gap-3 justify-end">
              <span className="text-[7px] md:text-[9px] text-white/40 font-mono tracking-widest uppercase text-right whitespace-nowrap">{s.label}</span>
              <div className={`w-1 md:w-1.5 h-1 md:h-1.5 rotate-45 ${s.active ? 'bg-cyan-400 shadow-[0_0_8px_#22d3ee]' : 'bg-red-500 shadow-[0_0_8px_#ef4444] animate-pulse'}`} />
            </div>
            <div className="flex items-center gap-2 justify-end">
              {s.active && <div className="hidden xs:block h-[1px] w-8 md:w-24 bg-gradient-to-l from-cyan-500/30 to-transparent" />}
              <span className={`text-[9px] md:text-[13px] font-black font-mono tracking-wide text-right ${s.active ? 'text-cyan-200' : 'text-red-400'}`}>
                {s.value}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Data Feed Decoration (Hidden on very small screens) */}
      <div className="mt-2 md:mt-4 flex flex-col gap-1 opacity-20 hidden sm:flex items-end">
        <div className="text-[6px] md:text-[7px] text-cyan-300 font-mono tracking-tight uppercase text-right">Lat_Buffer: 24ms // Pkt_Loss: 0.00%</div>
      </div>

      {/* Holographic Bracket Overlay */}
      <div className="absolute -top-4 -right-2 md:-right-4 w-8 md:w-12 h-8 md:h-12 border-t border-r border-cyan-500/20" />
    </div>
  );
};

export default StatusPanel;