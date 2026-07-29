import React, { useState, useEffect } from 'react';

export default function About() {
    const [counters, setCounters] = useState({
        uptime: 0,
        response: 0,
        support: 0,
        requests: 0
    });

    // Animated counter effect
    useEffect(() => {
        const animateCounter = (key, target, suffix = '') => {
            let start = 0;
            const duration = 2000;
            const step = (timestamp) => {
                if (!start) start = timestamp;
                const progress = Math.min((timestamp - start) / duration, 1);
                const value = Math.floor(progress * target);
                setCounters(prev => ({ ...prev, [key]: value }));
                if (progress < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
        };

        animateCounter('uptime', 999);
        animateCounter('response', 100);
        animateCounter('support', 247);
        animateCounter('requests', 50);
    }, []);

    const teamStats = [
        { key: 'uptime', value: counters.uptime, label: 'Uptime', icon: '📈', suffix: '.9%' },
        { key: 'response', value: counters.response, label: 'Response Time', icon: '⚡', suffix: 'ms' },
        { key: 'support', value: counters.support, label: 'Support', icon: '🛡️', suffix: '/7' },
        { key: 'requests', value: counters.requests, label: 'Requests Served', icon: '🌍', suffix: 'M+' }
    ];

    const features = [
        {
            icon: '🧠',
            title: 'Neural Intelligence',
            desc: 'Advanced deep learning models for contextual understanding and natural conversation.',
            gradient: 'from-purple-500 to-pink-500'
        },
        {
            icon: '⚡',
            title: 'Real-time Processing',
            desc: 'Ultra-low latency WebSocket connections for instantaneous responses.',
            gradient: 'from-cyan-500 to-blue-500'
        },
        {
            icon: '🔒',
            title: 'Secure & Private',
            desc: 'Enterprise-grade end-to-end encryption protects your sensitive data.',
            gradient: 'from-emerald-500 to-teal-500'
        },
        {
            icon: '🎨',
            title: 'Dynamic UI',
            desc: 'Audio-reactive WebGL visualizations that respond to your voice.',
            gradient: 'from-orange-500 to-red-500'
        },
        {
            icon: '🤖',
            title: 'Multi-modal AI',
            desc: 'Seamless integration of voice, text, and visual inputs.',
            gradient: 'from-indigo-500 to-purple-500'
        },
        {
            icon: '🌐',
            title: 'Multi-language',
            desc: 'Support for 50+ languages with real-time translation.',
            gradient: 'from-rose-500 to-pink-600'
        }
    ];

    const techStack = [
        { name: 'React 18', color: 'from-sky-500 to-blue-600' },
        { name: 'Three.js', color: 'from-emerald-500 to-teal-600' },
        { name: 'Tailwind CSS', color: 'from-cyan-500 to-blue-600' },
        { name: 'WebGL', color: 'from-purple-500 to-indigo-600' },
        { name: 'Node.js', color: 'from-green-500 to-emerald-600' },
        { name: 'WebSocket', color: 'from-orange-500 to-red-600' }
    ];

    return (
        <div className="relative min-h-screen w-full overflow-y-auto z-10">
            {/* Premium Animated Background */}
            <div className="fixed inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950"></div>

            {/* Animated Gradient Orbs */}
            <div className="fixed top-0 left-0 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-15 animate-pulse"></div>
            <div className="fixed bottom-0 right-0 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-15 animate-pulse delay-1000"></div>
            <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-[120px] opacity-10"></div>

            {/* Grid Pattern */}
            <div className="fixed inset-0 bg-[linear-gradient(to_right,#4f4f4f08_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f08_1px,transparent_1px)] bg-[size:40px_40px]"></div>

            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 pt-24 relative">

                {/* Hero Section */}
                <div className="text-center mb-16 animate-fadeInUp">
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 bg-cyan-500/10 backdrop-blur-sm border border-cyan-500/20 rounded-full px-5 py-2 mb-6 hover:border-cyan-500/40 transition-all duration-300">
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></div>
                        <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">Introducing v4.0</span>
                    </div>

                    {/* Title with Glow Effect */}
                    <h1 className="text-5xl md:text-7xl lg:text-8xl font-extrabold mb-6 relative">
                        <span className="bg-gradient-to-r from-white via-cyan-300 to-cyan-500 bg-clip-text text-transparent animate-gradient bg-[length:200%_auto]">
                            Brahmastra AI
                        </span>
                    </h1>

                    {/* Subtitle */}
                    <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
                        The next evolution of <span className="text-cyan-400 font-semibold">artificial intelligence</span> assistance
                    </p>
                </div>

                {/* Stats Section with Hover Effects */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-24">
                    {teamStats.map((stat, idx) => (
                        <div key={idx} className="group relative animate-fadeInUp" style={{ animationDelay: `${idx * 100}ms` }}>
                            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                            <div className="relative bg-gradient-to-br from-white/5 to-white/0 backdrop-blur-md rounded-2xl p-6 text-center border border-white/10 hover:border-cyan-500/40 transition-all duration-300 hover:translate-y-[-2px]">
                                <span className="text-4xl mb-3 block group-hover:scale-110 transition-transform duration-300">{stat.icon}</span>
                                <div className="flex items-baseline justify-center gap-1">
                                    <span className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                                        {stat.value}
                                    </span>
                                    <span className="text-base text-cyan-400/70 font-mono">{stat.suffix}</span>
                                </div>
                                <div className="text-xs text-slate-500 font-mono mt-2 uppercase tracking-wider">{stat.label}</div>
                                {/* Progress Bar */}
                                <div className="mt-3 h-0.5 bg-white/10 rounded-full overflow-hidden">
                                    <div className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full animate-progress" style={{ width: '70%' }}></div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Mission Section - Enhanced */}
                <div className="relative mb-24">
                    <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-transparent to-blue-500/20 rounded-3xl blur-2xl animate-pulse"></div>
                    <div className="relative bg-gradient-to-br from-white/10 to-white/5 backdrop-blur-xl rounded-3xl border border-white/10 p-10 md:p-14 text-center hover:border-cyan-500/30 transition-all duration-500">
                        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center shadow-xl shadow-cyan-500/30 group-hover:scale-110 transition-transform">
                            <span className="text-3xl">🎯</span>
                        </div>
                        <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">Our Mission</h2>
                        <p className="text-slate-300 text-lg md:text-xl max-w-4xl mx-auto leading-relaxed">
                            To democratize advanced AI technology by creating an intelligent assistant that is
                            <span className="text-cyan-400 font-bold"> powerful, intuitive, and accessible</span> to everyone,
                            while maintaining the highest standards of privacy and performance.
                        </p>
                    </div>
                </div>

                {/* Features Grid - Enhanced */}
                <div className="mb-24">
                    <div className="text-center mb-12">
                        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Powered by Innovation</h2>
                        <div className="w-20 h-1 bg-gradient-to-r from-cyan-500 to-blue-500 mx-auto rounded-full"></div>
                        <p className="text-slate-400 mt-4">Cutting-edge technology for unparalleled performance</p>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature, idx) => (
                            <div key={idx} className="group relative animate-fadeInUp" style={{ animationDelay: `${idx * 100}ms` }}>
                                <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                                <div className="relative bg-gradient-to-br from-white/5 to-white/0 backdrop-blur-md rounded-2xl p-6 border border-white/10 hover:border-cyan-500/50 transition-all duration-300 hover:translate-y-[-4px] h-full">
                                    <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-5 group-hover:scale-110 transition-all duration-300 shadow-lg`}>
                                        <span className="text-2xl">{feature.icon}</span>
                                    </div>
                                    <h3 className="text-xl font-bold text-white mb-3">{feature.title}</h3>
                                    <p className="text-slate-400 text-sm leading-relaxed">{feature.desc}</p>
                                    {/* Decorative line */}
                                    <div className="mt-4 w-12 h-0.5 bg-gradient-to-r from-cyan-500 to-transparent rounded-full group-hover:w-20 transition-all duration-300"></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Tech Stack Section - Enhanced */}
                <div className="mb-20">
                    <div className="text-center mb-10">
                        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Technology Stack</h2>
                        <div className="w-20 h-1 bg-gradient-to-r from-cyan-500 to-blue-500 mx-auto rounded-full"></div>
                        <p className="text-slate-400 mt-4">Built with modern, battle-tested technologies</p>
                    </div>
                    <div className="flex flex-wrap justify-center gap-3">
                        {techStack.map((tech, idx) => (
                            <div key={idx} className="group">
                                <div className={`bg-gradient-to-r ${tech.color} px-5 py-2.5 rounded-full text-white text-sm font-medium shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 cursor-pointer`}>
                                    {tech.name}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* CTA Section - Enhanced */}
                <div className="text-center mb-16">
                    <div className="relative group">
                        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/30 to-blue-500/30 rounded-3xl blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="relative bg-gradient-to-r from-cyan-500/10 to-blue-500/10 backdrop-blur-xl rounded-3xl p-10 border border-white/20 hover:border-cyan-500/40 transition-all duration-500">
                            <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">Ready to experience the future?</h3>
                            <p className="text-slate-400 mb-8 text-lg">Join thousands of users who trust Brahmastra AI for their daily tasks</p>
                            <button className="relative group/btn overflow-hidden px-10 py-4 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full text-white font-bold text-lg hover:scale-105 transition-all duration-300 shadow-2xl shadow-cyan-500/30">
                                <span className="relative z-10 flex items-center gap-2">
                                    Get Started Now
                                    <span className="text-xl group-hover/btn:translate-x-1 transition-transform">→</span>
                                </span>
                                <div className="absolute inset-0 bg-gradient-to-r from-cyan-600 to-blue-700 translate-y-full group-hover/btn:translate-y-0 transition-transform duration-300"></div>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="text-center pt-8 border-t border-white/10">
                    <div className="flex flex-wrap justify-center gap-6 mb-6">
                        <span className="text-xs font-mono text-slate-500 hover:text-cyan-400 transition-all duration-300 cursor-pointer hover:translate-y-[-1px]">Documentation</span>
                        <span className="text-xs font-mono text-slate-500 hover:text-cyan-400 transition-all duration-300 cursor-pointer hover:translate-y-[-1px]">API Reference</span>
                        <span className="text-xs font-mono text-slate-500 hover:text-cyan-400 transition-all duration-300 cursor-pointer hover:translate-y-[-1px]">Support</span>
                        <span className="text-xs font-mono text-slate-500 hover:text-cyan-400 transition-all duration-300 cursor-pointer hover:translate-y-[-1px]">Privacy</span>
                        <span className="text-xs font-mono text-slate-500 hover:text-cyan-400 transition-all duration-300 cursor-pointer hover:translate-y-[-1px]">GitHub</span>
                    </div>
                    <p className="text-slate-600 text-xs font-mono">© 2024 Brahmastra AI. Built with ❤️ for the future of intelligence.</p>
                </div>
            </div>

            {/* Animation Styles */}
            <style jsx="true">{`
                @keyframes fadeInUp {
                    from {
                        opacity: 0;
                        transform: translateY(30px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                @keyframes gradient {
                    0%, 100% {
                        background-position: 0% 50%;
                    }
                    50% {
                        background-position: 100% 50%;
                    }
                }
                
                @keyframes progress {
                    0% {
                        width: 0%;
                    }
                    100% {
                        width: 70%;
                    }
                }
                
                .animate-fadeInUp {
                    animation: fadeInUp 0.6s ease-out forwards;
                    opacity: 0;
                }
                
                .animate-gradient {
                    background-size: 200% auto;
                    animation: gradient 3s ease infinite;
                }
                
                .animate-progress {
                    animation: progress 1.5s ease-out forwards;
                }
                
                .delay-1000 {
                    animation-delay: 1s;
                }
            `}</style>
        </div>
    );
}