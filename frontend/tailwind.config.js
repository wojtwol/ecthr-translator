/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'primary': {
          600: '#4F46E5',
        },
        'success': {
          500: '#22C55E',
        },
        'warning': {
          500: '#F59E0B',
        },
        'error': {
          500: '#EF4444',
        },
        'tm-exact': '#059669',
        'tm-fuzzy': '#D97706',
        'hudoc': '#7C3AED',
        'curia': '#2563EB',
        'proposed': '#6B7280',
      },
    },
  },
  plugins: [],
}
