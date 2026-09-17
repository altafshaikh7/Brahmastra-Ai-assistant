import { useEffect, useState } from 'react';
import Navbar from './component/Navbar';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import SettingsPopup from './pages/SettingsPopup';
import About from './pages/About';
import Auth from './pages/Auth';
import SpeechTerminal from './component/SpeechTerminal';
import StatusPanel from './component/StatusPanel';
import { getSettings } from './services/settingsApi';
import { getBackendHealth } from './services/api';
import { getMe } from './services/authApi';

export default function App() {
  const [currentPage, setCurrentPage] = useState('Home');
  const [showSettingsPopup, setShowSettingsPopup] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  const [systemState, setSystemState] = useState({
    micStatus: 'DISABLED',
    apiStatus: 'CHECKING',
    aiStatus: 'UNKNOWN',
    authStatus: 'UNAUTHENTICATED',
    systemStatus: 'NOMINAL',
    isSpeaking: false,
    isProcessing: false,
    statusText: 'Initializing...'
  });

  const [blobSettings, setBlobSettings] = useState({
    color: '#0084ff',
    size: 1,
    position: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
    isDragging: false,
  });

  const handleStateChange = (updates) => {
    setSystemState(prev => ({ ...prev, ...updates }));
  };

  const handleLogin = () => {
    setIsAuthenticated(true);
    handleStateChange({ authStatus: 'AUTHENTICATED' });
    fetchDBSettings();
  };

  const fetchDBSettings = async () => {
    try {
      const savedSettings = await getSettings();
      if (savedSettings) {
        setBlobSettings(prev => ({
          ...prev,
          color: savedSettings.color || prev.color,
          size: savedSettings.size || prev.size,
          sensitivity: savedSettings.sensitivity || prev.sensitivity,
          isDragging: savedSettings.isDragging !== undefined ? savedSettings.isDragging : prev.isDragging,
          position: savedSettings.position?.x !== undefined ? savedSettings.position : { x: window.innerWidth / 2, y: window.innerHeight / 2 },
        }));
      }
    } catch (err) {
      console.warn("Could not retrieve settings from MongoDB, falling back to local state:", err);
    }
  };

  // Fetch settings from MongoDB on initial mount
  useEffect(() => {
    getBackendHealth()
      .then(() => handleStateChange({ apiStatus: 'CONNECTED' }))
      .catch(() => handleStateChange({ apiStatus: 'OFFLINE', systemStatus: 'DEGRADED' }));

    const checkAuth = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const res = await getMe(token);
          if (res.success) {
            setIsAuthenticated(true);
            handleStateChange({ authStatus: 'AUTHENTICATED' });
            await fetchDBSettings();
          }
        } catch {
          localStorage.removeItem('token');
        }
      }
      setIsInitializing(false);
    };

    checkAuth();

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      handleStateChange({ authStatus: 'UNAUTHENTICATED' });
    };

    window.addEventListener('unauthorized', handleUnauthorized);
    return () => window.removeEventListener('unauthorized', handleUnauthorized);
  }, []);

  // Standard scripts loading and resize listener
  useEffect(() => {
    if (!document.querySelector('script[src="https://cdn.tailwindcss.com"]')) {
      const script = document.createElement('script');
      script.src = "https://cdn.tailwindcss.com";
      document.head.appendChild(script);
    }

    const handleResize = () => {
      if (!blobSettings.isDragging) {
        setBlobSettings(prev => ({
          ...prev,
          position: { x: window.innerWidth / 2, y: window.innerHeight / 2 }
        }));
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [blobSettings.isDragging]);

  const renderPage = () => {
    switch (currentPage) {
      case 'Home':
        return <Home blobSettings={blobSettings} setBlobSettings={setBlobSettings} />;
      case 'Dashboard':
        return <Dashboard />;
      case 'About':
        return <About />;
      default:
        return <Home blobSettings={blobSettings} setBlobSettings={setBlobSettings} />;
    }
  };

  if (isInitializing) {
    return <div className="min-h-screen bg-[#020617] text-white flex items-center justify-center">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Auth onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-[#020617] font-sans text-slate-100 overflow-hidden relative">
      {/* Cinematic Background Gradient */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(15,23,42,1)_0%,rgba(2,6,23,1)_100%)] z-[-1]" />

      <Navbar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        blobSettings={blobSettings}
        setBlobSettings={setBlobSettings}
        setShowSettingsPopup={setShowSettingsPopup}
      />

      <StatusPanel systemState={systemState} />

      <main className="relative z-10 h-screen w-full overflow-y-auto pb-48">
        {renderPage()}
      </main>

      <SpeechTerminal onStateChange={handleStateChange} />

      {/* Futuristic Grid Overlay */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-[0.03] bg-[linear-gradient(to_right,#00f2ff_1px,transparent_1px),linear-gradient(to_bottom,#00f2ff_1px,transparent_1px)] bg-[size:60px_60px]" />

      {showSettingsPopup && (
        <SettingsPopup
          blobSettings={blobSettings}
          setBlobSettings={setBlobSettings}
          onClose={() => setShowSettingsPopup(false)}
        />
      )}
    </div>
  );
}
