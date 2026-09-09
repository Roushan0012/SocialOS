import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#090B0E",
        surface: "#0E1217",
        surfaceCard: "#141922",
        borderSubtle: "#212836",
        brandPrimary: "#6366F1",
      },
    },
  },
  plugins: [],
};

export default config;
