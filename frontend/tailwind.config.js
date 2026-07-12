/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // The whole app is built on Tailwind's zinc scale + literal white/black
        // for chrome (900+ usages). Re-pointing those tokens at CSS variables
        // (see index.css) makes every existing class theme-aware for free --
        // no per-component edits -- while the "<alpha-value>" placeholder keeps
        // opacity modifiers like bg-zinc-900/40 working.
        white: 'rgb(var(--c-white) / <alpha-value>)',
        black: 'rgb(var(--c-black) / <alpha-value>)',
        zinc: {
          50: 'rgb(var(--c-zinc-50) / <alpha-value>)',
          100: 'rgb(var(--c-zinc-100) / <alpha-value>)',
          200: 'rgb(var(--c-zinc-200) / <alpha-value>)',
          300: 'rgb(var(--c-zinc-300) / <alpha-value>)',
          400: 'rgb(var(--c-zinc-400) / <alpha-value>)',
          500: 'rgb(var(--c-zinc-500) / <alpha-value>)',
          600: 'rgb(var(--c-zinc-600) / <alpha-value>)',
          700: 'rgb(var(--c-zinc-700) / <alpha-value>)',
          800: 'rgb(var(--c-zinc-800) / <alpha-value>)',
          900: 'rgb(var(--c-zinc-900) / <alpha-value>)',
          950: 'rgb(var(--c-zinc-950) / <alpha-value>)',
        },
        // Fixed (non-inverting) ink for badges painted on a fixed accent
        // background (e.g. bg-amber-400 text-badgeink) -- those need dark text
        // in both themes since the accent color itself doesn't change.
        badgeink: '#09090b',
        // Same idea, inverse: fixed light text for buttons on saturated
        // mid-tone accent backgrounds (e.g. bg-blue-600 text-onaccent) --
        // those need light text in both themes.
        onaccent: '#fafafa',
        // Chrome (header/left-nav rail/sidebar/footer) background -- a
        // dedicated token so these regions stay visibly distinct from the
        // canvas in light mode without changing the already-correct dark
        // mode, where it equals zinc-950 (see index.css).
        chrome: 'rgb(var(--c-chrome) / <alpha-value>)',
      },
    },
  },
  plugins: [],
};
