import type { InputHTMLAttributes } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export function Input({ label, error, id, className = "", ...rest }: Props) {
  const inputId = id || label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="space-y-1">
      <label htmlFor={inputId} className="block text-sm text-navy-muted">
        {label}
      </label>
      <input
        id={inputId}
        className={`w-full px-3 py-2 border rounded text-sm text-ink bg-white ${
          error ? "border-danger" : "border-line"
        } focus:border-navy ${className}`}
        {...rest}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}
