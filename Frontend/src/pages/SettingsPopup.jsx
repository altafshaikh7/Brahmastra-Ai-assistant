import React, { useState } from 'react';
import { updateSettings } from '../services/settingsApi';

export default function SettingsPopup({ blobSettings, setBlobSettings, onClose }) {
    const [localSettings, setLocalSettings] = useState({
        color: blobSettings.color,
        size: blobSettings.size,
        sensitivity: blobSettings.sensitivity || 1.2,
        isDragging: blobSettings.isDragging,
    });

    const handleSave = async () => {
        try {
            const newSettings = {
                color: localSettings.color,
                size: localSettings.size,
                sensitivity: localSettings.sensitivity,
                isDragging: localSettings.isDragging,
                position: blobSettings.position, // Keep current position
            };
            
            const savedData = await updateSettings(newSettings);
            
            setBlobSettings((prev) => ({
                ...prev,
                ...savedData,
            }));
            
            onClose();
        } catch (err) {
            console.error("Failed to save settings to MongoDB:", err);
        }
    };

    const handleReset = async () => {
        const resetSettings = {
            color: '#0084ff',
            size: 1,
            sensitivity: 1.2,
            isDragging: false,
            position: { x: window.innerWidth / 2, y: window.innerHeight / 2 }
        };

        try {
            const savedData = await updateSettings(resetSettings);
            setLocalSettings({
                color: savedData.color,
                size: savedData.size,
                sensitivity: savedData.sensitivity,
                isDragging: savedData.isDragging,
            });
            setBlobSettings(savedData);
        } catch (err) {
            console.error("Failed to reset settings in MongoDB:", err);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={onClose}></div>

            {/* Popup Content */}
            <div className="relative bg-gradient-to-br from-slate-900 to-slate-950 rounded-2xl border border-white/20 shadow-2xl shadow-cyan-500/20 w-full max-w-md p-6">

                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 flex items-center justify-center">
                            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">Blob Settings</h2>
                            <p className="text-xs text-slate-400">Customize your visualizer</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition p-1">
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Settings Content */}
                <div className="space-y-5">
                    {/* Color Theme */}
                    <div>
                        <label className="text-sm text-slate-300 block mb-2">🎨 Color Theme</label>
                        <div className="flex flex-wrap gap-3">
                            {['#0084ff', '#00ffe1', '#b800ff', '#ff00aa', '#ff6600', '#00ff88'].map(color => (
                                <div
                                    key={color}
                                    onClick={() => setLocalSettings(prev => ({ ...prev, color }))}
                                    className="w-10 h-10 rounded-full cursor-pointer hover:scale-110 transition-all duration-200 shadow-lg"
                                    style={{
                                        background: color,
                                        border: localSettings.color === color ? '3px solid white' : '2px solid transparent',
                                        boxShadow: localSettings.color === color ? `0 0 15px ${color}` : 'none'
                                    }}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Size Control */}
                    <div>
                        <div className="flex justify-between mb-1">
                            <label className="text-sm text-slate-300">📏 Size</label>
                            <span className="text-xs text-cyan-400 font-mono">{localSettings.size.toFixed(1)}x</span>
                        </div>
                        <input
                            type="range"
                            min="0.5"
                            max="2.5"
                            step="0.05"
                            value={localSettings.size}
                            onChange={(e) => setLocalSettings(prev => ({ ...prev, size: parseFloat(e.target.value) }))}
                            className="w-full accent-cyan-500 cursor-pointer h-2 rounded-lg"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                            <span>Small</span>
                            <span>Normal</span>
                            <span>Large</span>
                        </div>
                    </div>

                    {/* Sensitivity Control (Audio Reactivity) */}
                    <div>
                        <div className="flex justify-between mb-1">
                            <label className="text-sm text-slate-300">🎤 Audio Sensitivity</label>
                            <span className="text-xs text-purple-400 font-mono">{localSettings.sensitivity.toFixed(1)}x</span>
                        </div>
                        <input
                            type="range"
                            min="0.5"
                            max="2.5"
                            step="0.05"
                            value={localSettings.sensitivity}
                            onChange={(e) => setLocalSettings(prev => ({ ...prev, sensitivity: parseFloat(e.target.value) }))}
                            className="w-full accent-purple-500 cursor-pointer h-2 rounded-lg"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                            <span>Less Reactive</span>
                            <span>Normal</span>
                            <span>Very Reactive</span>
                        </div>
                    </div>

                    {/* Move Blob Toggle */}
                    <div className="flex items-center justify-between py-3 border-t border-b border-white/10">
                        <div>
                            <span className="text-sm text-white">🖱️ Move Blob</span>
                            <p className="text-[10px] text-slate-500">Enable to reposition the blob</p>
                        </div>
                        <button
                            onClick={() => setLocalSettings(prev => ({ ...prev, isDragging: !prev.isDragging }))}
                            className={`relative w-12 h-6 rounded-full transition-all duration-300 ${localSettings.isDragging ? 'bg-emerald-500' : 'bg-slate-600'}`}
                        >
                            <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all duration-300 ${localSettings.isDragging ? 'right-0.5' : 'left-0.5'}`} />
                        </button>
                    </div>

                    {/* Buttons */}
                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={handleReset}
                            className="flex-1 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-300 text-sm font-medium hover:bg-white/10 transition-all"
                        >
                            Reset to Default
                        </button>
                        <button
                            onClick={handleSave}
                            className="flex-1 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-bold hover:scale-105 transition-all shadow-lg shadow-cyan-500/30"
                        >
                            Save Changes
                        </button>
                    </div>
                </div>

                {/* Live Preview Indicator */}
                <div className="mt-4 pt-3 border-t border-white/10 text-center">
                    <p className="text-[9px] text-slate-500 font-mono">
                        💾 Changes are automatically saved to MongoDB
                    </p>
                </div>
            </div>
        </div>
    );
}