import { useState, useEffect } from 'react';
import { Download, X, Share, ExternalLink } from 'lucide-react';

const DISMISS_KEY = 'install-prompt-dismissed';

const isStandalone = () =>
  window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

const isInAppBrowser = () => {
  const ua = navigator.userAgent || '';
  return /FBAN|FBAV|Instagram|WhatsApp|Line\/|Twitter|Snapchat|LinkedInApp/i.test(ua);
};

const isIOS = () => /iPhone|iPad|iPod/i.test(navigator.userAgent);

export const InstallPrompt = () => {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [mode, setMode] = useState(null); // 'install' | 'ios' | 'inapp'

  useEffect(() => {
    if (isStandalone() || localStorage.getItem(DISMISS_KEY)) return;

    if (isInAppBrowser()) {
      setMode('inapp');
      return;
    }

    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setMode('install');
    };
    window.addEventListener('beforeinstallprompt', handler);

    if (isIOS()) setMode('ios');

    window.addEventListener('appinstalled', () => setMode(null));
    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') setMode(null);
    setDeferredPrompt(null);
  };

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1');
    setMode(null);
  };

  if (!mode) return null;

  return (
    <div
      data-testid="install-prompt-banner"
      className="fixed left-3 right-3 z-50 rounded-xl shadow-lg p-3.5 flex items-center gap-3"
      style={{
        bottom: 'calc(76px + env(safe-area-inset-bottom, 0px))',
        backgroundColor: '#0D1B2A',
        color: '#FFFFFF',
        maxWidth: 480,
        margin: '0 auto',
      }}
    >
      <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }}>
        {mode === 'inapp' ? <ExternalLink className="w-5 h-5" /> : mode === 'ios' ? <Share className="w-5 h-5" /> : <Download className="w-5 h-5" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold leading-tight">THE MANAGER app install karein</p>
        <p className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.65)' }}>
          {mode === 'inapp' && 'Ye link browser me kholein (⋮ menu → "Open in Chrome"), phir install option milega'}
          {mode === 'ios' && 'Safari me Share button dabayein, phir "Add to Home Screen" select karein'}
          {mode === 'install' && 'Home screen se seedha app ki tarah use karein'}
        </p>
      </div>
      {mode === 'install' && (
        <button
          onClick={handleInstall}
          data-testid="install-app-btn"
          className="shrink-0 px-3.5 py-2 rounded-lg text-[12px] font-semibold"
          style={{ backgroundColor: '#FFFFFF', color: '#0D1B2A' }}
        >
          Install
        </button>
      )}
      <button onClick={dismiss} data-testid="install-dismiss-btn" aria-label="Dismiss"
        className="shrink-0 p-1.5 rounded-md" style={{ color: 'rgba(255,255,255,0.6)' }}>
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
