import { useState, useEffect, useRef } from 'react';
import { Navigation, LocateFixed, Loader2, MapPin } from 'lucide-react';
import { toast } from 'sonner';

const NOMINATIM = 'https://nominatim.openstreetmap.org';

export const LocationPicker = ({ value, onChange, testIdPrefix = 'location' }) => {
  const [query, setQuery] = useState(value || '');
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const debounceRef = useRef(null);
  const wrapRef = useRef(null);
  const skipSearchRef = useRef(false);

  useEffect(() => { setQuery(value || ''); }, [value]);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const handleInput = (e) => {
    const text = e.target.value;
    setQuery(text);
    onChange({ address: text, lat: null, lng: null });
    if (skipSearchRef.current) { skipSearchRef.current = false; return; }
    clearTimeout(debounceRef.current);
    if (text.trim().length < 3) { setSuggestions([]); setOpen(false); return; }
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`${NOMINATIM}/search?format=json&addressdetails=1&limit=5&countrycodes=in&q=${encodeURIComponent(text)}`);
        const data = await res.json();
        setSuggestions(data);
        setOpen(data.length > 0);
      } catch {
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 450);
  };

  const selectSuggestion = (s) => {
    skipSearchRef.current = true;
    setQuery(s.display_name);
    onChange({ address: s.display_name, lat: parseFloat(s.lat), lng: parseFloat(s.lon) });
    setOpen(false);
    setSuggestions([]);
  };

  const detectLocation = () => {
    if (!navigator.geolocation) {
      toast.error('Aapke browser me location support nahi hai');
      return;
    }
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const res = await fetch(`${NOMINATIM}/reverse?format=json&lat=${latitude}&lon=${longitude}`);
          const data = await res.json();
          const address = data.display_name || `${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
          skipSearchRef.current = true;
          setQuery(address);
          onChange({ address, lat: latitude, lng: longitude });
          toast.success('Current location detect ho gayi');
        } catch {
          toast.error('Address fetch nahi ho paya, dobara try karein');
        } finally {
          setDetecting(false);
        }
      },
      (err) => {
        setDetecting(false);
        if (err.code === 1) toast.error('Location permission denied — browser me location allow karein');
        else toast.error('Location detect nahi ho payi');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return (
    <div ref={wrapRef} className="relative">
      <div className="relative">
        <Navigation className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input type="text" value={query} onChange={handleInput}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          data-testid={`${testIdPrefix}-input`}
          className="input-field w-full pl-10 pr-11" placeholder="Location search karein ya GPS use karein" required />
        <button type="button" onClick={detectLocation} disabled={detecting}
          data-testid={`${testIdPrefix}-gps-btn`} title="Use current location"
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-accent hover:bg-accent/10 transition-colors disabled:opacity-50">
          {detecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <LocateFixed className="w-4 h-4" />}
        </button>
      </div>
      {searching && (
        <p className="text-xs text-text-muted mt-1 flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" /> Searching...
        </p>
      )}
      {open && suggestions.length > 0 && (
        <div data-testid={`${testIdPrefix}-suggestions`}
          className="absolute z-50 mt-1 w-full bg-bg-surface border border-border-color rounded-lg shadow-lg max-h-56 overflow-y-auto">
          {suggestions.map((s) => (
            <button key={s.place_id} type="button" onClick={() => selectSuggestion(s)}
              className="w-full flex items-start gap-2 px-3 py-2.5 text-left hover:bg-bg-elevated transition-colors border-b border-border-color last:border-b-0">
              <MapPin className="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <span className="text-sm text-text-primary line-clamp-2">{s.display_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
