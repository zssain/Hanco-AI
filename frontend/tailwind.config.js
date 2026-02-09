/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f8f9fa',
          100: '#f1f3f5',
          200: '#e9ecef',
          300: '#dee2e6',
          400: '#ced4da',
          500: '#868e96',
          600: '#495057',
          700: '#343a40',
          800: '#212529',
          900: '#16191d',
          950: '#0d0f12',
        },
        accent: {
          50: '#f0f4ff',
          100: '#d6e4ff',
          200: '#adc8ff',
          300: '#84a9ff',
          400: '#5b8def',
          500: '#3b71d9',
          600: '#2f5bb8',
          700: '#244796',
          800: '#1a3370',
          900: '#112150',
        },
        dark: {
          50: '#1a1d21',
          100: '#141719',
          200: '#0f1113',
          300: '#0b0d0e',
          400: '#060708',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans Arabic', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'hero-gradient': 'linear-gradient(135deg, #0b0d0e 0%, #141719 50%, #0b0d0e 100%)',
        'card-gradient': 'linear-gradient(180deg, rgba(59, 113, 217, 0.04) 0%, rgba(59, 113, 217, 0.01) 100%)',
        'glow-gradient': 'linear-gradient(135deg, rgba(59, 113, 217, 0.08) 0%, rgba(59, 113, 217, 0.04) 50%, transparent 100%)',
      },
      boxShadow: {
        'glow': '0 0 60px -12px rgba(59, 113, 217, 0.15)',
        'glow-sm': '0 0 30px -8px rgba(59, 113, 217, 0.1)',
        'glow-lg': '0 0 100px -20px rgba(59, 113, 217, 0.2)',
        'card': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)',
        'card-hover': '0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 4px 10px -4px rgba(0, 0, 0, 0.08)',
        'soft': '0 2px 8px rgba(0, 0, 0, 0.04)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'gradient': 'gradient 8s linear infinite',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-down': 'slideDown 0.5s ease-out',
        'fade-in': 'fadeIn 0.5s ease-out',
        'scale-in': 'scaleIn 0.3s ease-out',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        },
        gradient: {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}
