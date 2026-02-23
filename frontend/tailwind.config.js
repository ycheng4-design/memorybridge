/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'memory-bg': '#0f0a1e',
        'memory-bg-secondary': '#1a1035',
        'memory-bg-card': '#231850',
        'memory-accent': '#f4c430',
        'memory-accent-dim': '#c9992a',
        'memory-accent-glow': 'rgba(244, 196, 48, 0.3)',
        'memory-purple': '#6d28d9',
        'memory-purple-light': '#8b5cf6',
        'memory-blue': '#1d4ed8',
        'memory-text': '#e8e0f5',
        'memory-text-muted': '#9187b0',
        'memory-glass': 'rgba(255, 255, 255, 0.08)',
        'memory-glass-border': 'rgba(255, 255, 255, 0.12)',
      },
      fontFamily: {
        heading: ['Inter', 'system-ui', 'sans-serif'],
        body: ['system-ui', '-apple-system', 'sans-serif'],
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(15, 10, 30, 0.6)',
        'glow-gold': '0 0 20px rgba(244, 196, 48, 0.4), 0 0 40px rgba(244, 196, 48, 0.1)',
        'glow-purple': '0 0 20px rgba(109, 40, 217, 0.4), 0 0 40px rgba(109, 40, 217, 0.1)',
        'card-hover': '0 20px 60px rgba(15, 10, 30, 0.8), 0 0 20px rgba(244, 196, 48, 0.15)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'float-delayed': 'float 6s ease-in-out 2s infinite',
        'float-slow': 'float 8s ease-in-out 1s infinite',
        'memory-entrance': 'memoryEntrance 0.5s ease-out forwards',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'waveform': 'waveform 0.8s ease-in-out infinite alternate',
        'shimmer': 'shimmer 2s linear infinite',
        'spin-slow': 'spin 4s linear infinite',
        'fade-in': 'fadeIn 0.3s ease-out forwards',
        'slide-up': 'slideUp 0.4s ease-out forwards',
        'orb-pulse': 'orbPulse 3s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        memoryEntrance: {
          '0%': { opacity: '0', transform: 'translateY(24px) scale(0.96)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        pulseGlow: {
          '0%, 100%': {
            boxShadow: '0 0 10px rgba(244, 196, 48, 0.3), 0 0 20px rgba(244, 196, 48, 0.1)',
          },
          '50%': {
            boxShadow: '0 0 25px rgba(244, 196, 48, 0.6), 0 0 50px rgba(244, 196, 48, 0.2)',
          },
        },
        waveform: {
          '0%': { transform: 'scaleY(0.3)' },
          '100%': { transform: 'scaleY(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        orbPulse: {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.12)', opacity: '1' },
        },
      },
      backgroundImage: {
        'shimmer-gradient':
          'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 50%, transparent 100%)',
        'radial-glow':
          'radial-gradient(ellipse at center, rgba(109, 40, 217, 0.15) 0%, transparent 70%)',
        'gold-glow':
          'radial-gradient(ellipse at center, rgba(244, 196, 48, 0.2) 0%, transparent 60%)',
      },
      transitionDuration: {
        '200': '200ms',
        '300': '300ms',
      },
    },
  },
  plugins: [],
}
