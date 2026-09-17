import { useState, useEffect } from 'react';
import { getBackendHealth } from '../services/api';

export default function Dashboard() {
    const [health, setHealth] = useState({ status: 'checking' });

    useEffect(() => {
        getBackendHealth().then(setHealth).catch(() => setHealth({ status: 'offline' }));
    }, []);

    const cards = [
        { title: 'Backend', value: health.status?.toUpperCase() || 'UNKNOWN', icon: '◉', color: 'from-cyan-500 to-blue-500' },
        { title: 'AI metrics', value: 'NOT AVAILABLE', icon: '—', color: 'from-slate-500 to-slate-700' },
        { title: 'User metrics', value: 'NOT AVAILABLE', icon: '—', color: 'from-slate-500 to-slate-700' },
        { title: 'Request metrics', value: 'NOT AVAILABLE', icon: '—', color: 'from-slate-500 to-slate-700' }
    ];

    return (
        <div className="relative h-screen w-full overflow-y-auto p-6">
            <div className="max-w-7xl mx-auto">
                <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">Dashboard</h1>
                <p className="text-slate-400 mb-8">Real-time AI performance metrics</p>

                {/* Stats Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    {cards.map((card, idx) => (
                        <div key={idx} className={`bg-gradient-to-br ${card.color} p-6 rounded-2xl shadow-xl backdrop-blur-sm`}>
                            <div className="flex items-center justify-between">
                                <span className="text-3xl">{card.icon}</span>
                                <span className="text-2xl font-bold text-white">{card.value}</span>
                            </div>
                            <p className="text-white/80 mt-2 text-sm">{card.title}</p>
                        </div>
                    ))}
                </div>

                {/* Activity Chart Placeholder */}
                <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/10 p-6">
                    <h2 className="text-xl font-bold text-white mb-4">Activity Overview</h2>
                    <div className="h-64 flex items-center justify-center border border-white/10 rounded-xl bg-white/5">
                        <p className="text-slate-400">📊 Chart visualization coming soon</p>
                    </div>
                </div>
            </div>
        </div>
    );
}