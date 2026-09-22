import type { ButtonHTMLAttributes } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
}

const variants = {
  primary: "bg-navy text-white hover:bg-navy-light disabled:bg-navy-muted",
  secondary: "bg-white text-navy border border-line hover:border-navy disabled:text-navy-muted",
  danger: "bg-danger text-white hover:opacity-90 disabled:opacity-50",
};

export function Button({ variant = "primary", loading, disabled, className = "", children, ...rest }: Props) {
  return (
    <button
      disabled={disabled || loading}
      className={`px-4 py-2 rounded text-sm font-medium transition-colors disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...rest}
    >
      {loading ? "Please wait…" : children}
    </button>
  );
}
