import { useEffect, useState, type ReactNode } from "react";
import { apiClient } from "@/api/client";

/** Renders an image from an endpoint that requires the bearer token —
 * `<img src>` can't attach an Authorization header itself, so this fetches
 * the bytes via apiClient (which does) and hands the browser a local
 * blob: URL instead. Used for payment proof files (audit fix: these used
 * to be served by a public, unauthenticated static mount) and for a
 * user's own profile photo in the sidebar.
 *
 * `fallback` overrides the default "Couldn't load image." text for a
 * 404/error — used by the sidebar avatar to silently show the default
 * logo instead, where a text error would break a small circular layout. */
export function AuthenticatedImage({
  src, alt, className, fallback,
}: { src: string; alt: string; className?: string; fallback?: ReactNode }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let url: string | null = null;
    setObjectUrl(null);
    setError(false);

    apiClient
      .get(src, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        url = URL.createObjectURL(res.data as Blob);
        setObjectUrl(url);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [src]);

  if (error) return <>{fallback ?? <p className="text-sm text-danger">Couldn't load image.</p>}</>;
  if (!objectUrl) {
    return <div className={className ? `${className} bg-line/50 animate-pulse` : "h-40 w-full rounded border border-line bg-line/50 animate-pulse"} />;
  }
  return <img src={objectUrl} alt={alt} className={className} />;
}
