import { useEffect, useState } from "react";
import { apiClient } from "@/api/client";

/** Renders an image from an endpoint that requires the bearer token —
 * `<img src>` can't attach an Authorization header itself, so this fetches
 * the bytes via apiClient (which does) and hands the browser a local
 * blob: URL instead. Used for payment proof files (audit fix: these used
 * to be served by a public, unauthenticated static mount). */
export function AuthenticatedImage({ src, alt, className }: { src: string; alt: string; className?: string }) {
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

  if (error) return <p className="text-sm text-danger">Couldn't load image.</p>;
  if (!objectUrl) return <div className="h-40 w-full rounded border border-line bg-line/50 animate-pulse" />;
  return <img src={objectUrl} alt={alt} className={className} />;
}
