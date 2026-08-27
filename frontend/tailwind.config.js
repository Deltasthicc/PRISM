/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,jsx}', './components/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Kept in lockstep with the --color-* vars in app/globals.css --
        // Tailwind's utility classes (bg-stone, border-arcane, etc.) read
        // from here, not from the CSS vars, so both must be updated together.
        void: '#0a0908',
        stone: {
          DEFAULT: '#201b16',
          dark: '#18140f',
          light: '#362f27',
        },
        ember: {
          DEFAULT: '#ff6b3d',
          dim: '#b8492a',
        },
        arcane: {
          DEFAULT: '#6ee7d0',
          dim: '#3a8c7c',
        },
        gold: {
          DEFAULT: '#e8b339',
          dim: '#a87f22',
        },
        parchment: {
          DEFAULT: '#ece3cf',
          dim: '#a89f8c',
        },
        blood: '#c43d3d',
      },
      fontFamily: {
        display: ['"Press Start 2P"', 'cursive'],
        body: ['"VT323"', 'monospace'],
      },
      boxShadow: {
        'pixel-sm': '2px 2px 0 0 #000',
      },
      keyframes: {
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%': { transform: 'translateX(-4px)' },
          '40%': { transform: 'translateX(4px)' },
          '60%': { transform: 'translateX(-3px)' },
          '80%': { transform: 'translateX(3px)' },
        },
        flicker: {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.85 },
        },
      },
      animation: {
        shake: 'shake 0.4s ease-in-out',
        flicker: 'flicker 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
