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
                sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
                mono: ['"JetBrains Mono"', 'monospace'],
            },
            colors: {
                // Custom Housing Society Colors
                'bg-base': '#0D1B2A',
                'bg-surface': '#1A2B3C',
                'bg-elevated': '#243447',
                'accent': '#E67E22',
                'accent-hover': '#CA6F1E',
                'success': '#27AE60',
                'warning': '#F39C12',
                'danger': '#E74C3C',
                'info': '#2E86C1',
                'text-primary': '#ECF0F1',
                'text-secondary': '#AEB6BF',
                'text-muted': '#566573',
                'border-color': '#2E4057',
                'border-light': '#3D5166',
                
                // Shadcn overrides
                background: '#0D1B2A',
                foreground: '#ECF0F1',
                card: {
                    DEFAULT: '#1A2B3C',
                    foreground: '#ECF0F1'
                },
                popover: {
                    DEFAULT: '#1A2B3C',
                    foreground: '#ECF0F1'
                },
                primary: {
                    DEFAULT: '#E67E22',
                    foreground: '#FFFFFF'
                },
                secondary: {
                    DEFAULT: '#243447',
                    foreground: '#AEB6BF'
                },
                muted: {
                    DEFAULT: '#243447',
                    foreground: '#566573'
                },
                accent: {
                    DEFAULT: '#E67E22',
                    foreground: '#FFFFFF'
                },
                destructive: {
                    DEFAULT: '#E74C3C',
                    foreground: '#FFFFFF'
                },
                border: '#2E4057',
                input: '#2E4057',
                ring: '#E67E22',
                chart: {
                    '1': '#E67E22',
                    '2': '#27AE60',
                    '3': '#2E86C1',
                    '4': '#F39C12',
                    '5': '#9B59B6'
                }
            },
            borderRadius: {
                lg: '0.75rem',
                md: '0.5rem',
                sm: '0.25rem',
                xl: '1rem'
            },
            boxShadow: {
                'card': '0 8px 30px rgb(0,0,0,0.12)',
                'glow': '0 0 20px rgba(230,126,34,0.15)',
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
