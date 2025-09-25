/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f6f4ef",
        surface: "#fffcf7",
        ink: "#1c1917",
        muted: "#44403c",
        line: "#e7e5e4",
        danger: "#9f1239",
        ok: "#166534",
        brand: {
          DEFAULT: "#115e59",
          foreground: "#ffffff",
          pressed: "#134e4a",
        },
      },
      spacing: {
        "2xs": "4px",
        xs: "8px",
        sm: "12px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        "2xl": "48px",
        tap: "44px",
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "16px",
      },
      fontFamily: {
        sans: ['"Segoe UI"', '"Helvetica Neue"', "Arial", "sans-serif"],
      },
    },
  },
  plugins: [],
};
