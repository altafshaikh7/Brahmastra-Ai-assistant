import React, { useState, useEffect } from 'react';

export default function Dashboard() {
    const [stats, setStats] = useState({
        aiConfidence: 98.7,
        activeUsers: 1247,
        responseTime: 124,
        totalQueries: 45289
    });

    useEffect(() => {
        const interval = setInterval(() => {
            setStats(prev => ({
                aiConfidence: Math.min(99.9, prev.aiConfidence + (Math.random() - 0.5) * 0.3),
                activeUsers: prev.activeUsers + Math.floor(Math.random() * 10) - 3,
                responseTime: Math.max(80, prev.responseTime + Math.floor(Math.random() * 10) - 5),
                totalQueries: prev.totalQueries + Math.floor(Math.random() * 50)
            }));
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    const cards = [
        { title: 'AI Confidence', value: `${stats.aiConfidence.toFixed(1)}%`, icon: '🧠', color: 'from-purple-500 to-pink-500' },
        { title: 'Active Users', value: stats.activeUsers.toLocaleString(), icon: '👥', color: 'from-blue-500 to-cyan-500' },
        { title: 'Response Time', value: `${stats.responseTime}ms`, icon: '⚡', color: 'from-green-500 to-emerald-500' },
        { title: 'Total Queries', value: stats.totalQueries.toLocaleString(), icon: '💬', color: 'from-orange-500 to-red-500' }
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