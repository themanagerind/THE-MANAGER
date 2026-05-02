/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
        "./src/**/*.{js,jsx,ts,tsx}",
        "./public/index.html"
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
            colors: {
                // Role accents
                'role-platform': '#534AB7',
                'role-admin': '#185FA5',
                'role-subadmin': '#0F6E56',
                'role-resident': '#7F77DD',
                'role-manager': '#993C1D',
                // Sidebar
                'sidebar-bg': '#0F172A',
                // Semantic status
                'status-paid': '#3B6D11',
                'status-pending': '#854F0B',
                'status-overdue': '#A32D2D',
                'status-active': '#3B6D11',
                'status-blocked': '#A32D2D',
                // Semantic colors
                'sem-success': '#3B6D11',
                'sem-success-bg': '#EAF3DE',
                'sem-danger': '#A32D2D',
                'sem-danger-bg': '#FCEBEB',
                'sem-warning': '#854F0B',
                'sem-warning-bg': '#FAEEDA',
                'sem-info': '#0C447C',
                'sem-info-bg': '#E6F1FB',
                'sem-neutral': '#5F5E5A',
                'sem-neutral-bg': '#F1EFE8',
                // Light mode
                'page-bg': '#F8F8F6',
                'card-bg': '#FFFFFF',
                'surface': '#F1EFE8',
                'txt-primary': '#1A1A18',
                'txt-secondary': '#5F5E5A',
                'txt-muted': '#888780',
                'brd': 'rgba(0,0,0,0.10)',
                // Legacy compat aliases (mapped to new design system)
                'bg-base': '#F8F8F6',
                'bg-surface': '#FFFFFF',
                'bg-elevated': '#F1EFE8',
                'border-color': 'rgba(0,0,0,0.10)',
                'text-primary': '#1A1A18',
                'text-secondary': '#5F5E5A',
                'text-muted': '#888780',
                'success': '#3B6D11',
                'danger': '#A32D2D',
                'warning': '#854F0B',
                // Shadcn overrides
                background: 'hsl(var(--background))',
                foreground: 'hsl(var(--foreground))',
                card: {
                    DEFAULT: 'hsl(var(--card))',
                    foreground: 'hsl(var(--card-foreground))'
                },
                popover: {
                    DEFAULT: 'hsl(var(--popover))',
                    foreground: 'hsl(var(--popover-foreground))'
                },
                primary: {
                    DEFAULT: 'hsl(var(--primary))',
                    foreground: 'hsl(var(--primary-foreground))'
                },
                secondary: {
                    DEFAULT: 'hsl(var(--secondary))',
                    foreground: 'hsl(var(--secondary-foreground))'
                },
                muted: {
                    DEFAULT: 'hsl(var(--muted))',
                    foreground: 'hsl(var(--muted-foreground))'
                },
                accent: {
                    DEFAULT: 'hsl(var(--accent))',
                    foreground: 'hsl(var(--accent-foreground))'
                },
                destructive: {
                    DEFAULT: 'hsl(var(--destructive))',
                    foreground: 'hsl(var(--destructive-foreground))'
                },
                border: 'hsl(var(--border))',
                input: 'hsl(var(--input))',
                ring: 'hsl(var(--ring))',
            },
            borderRadius: {
                lg: '0.75rem',
                md: '0.5rem',
                sm: '0.25rem',
                xl: '1rem',
                'card': '12px',
                'btn': '8px',
                'pill': '20px',
            },
            borderWidth: {
                'thin': '0.5px',
            },
            boxShadow: {
                'card': '0 1px 3px rgba(0,0,0,0.06)',
                'card-hover': '0 4px 12px rgba(0,0,0,0.08)',
            },
            keyframes: {
                'accordion-down': {
                    from: { height: '0' },
                    to: { height: 'var(--radix-accordion-content-height)' }
                },
                'accordion-up': {
                    from: { height: 'var(--radix-accordion-content-height)' },
                    to: { height: '0' }
                },
                'fade-in': {
                    from: { opacity: '0', transform: 'translateY(10px)' },
                    to: { opacity: '1', transform: 'translateY(0)' }
                }
            },
            animation: {
                'accordion-down': 'accordion-down 0.2s ease-out',
                'accordion-up': 'accordion-up 0.2s ease-out',
                'fade-in': 'fade-in 0.3s ease-out'
            }
        }
    },
    plugins: [require("tailwindcss-animate")],
};
