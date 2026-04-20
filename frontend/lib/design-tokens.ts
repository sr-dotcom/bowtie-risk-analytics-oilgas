export const TOKENS = {
  bg: { base: '#0F1419', surface: '#151B24', elevated: '#1C2430', accent: '#1A2332' },
  border: { subtle: '#1F2937', default: '#2A3442', strong: '#3A4556' },
  text: { primary: '#E8E8E8', secondary: '#9CA3AF', tertiary: '#6B7280', inverse: '#0F1419' },
  risk: { high: '#C0392B', highText: '#E74C3C', medium: '#996515', mediumText: '#D68910', low: '#1F6F43', lowText: '#27AE60', unknown: '#4A5568' },
  accent: { primary: '#2C5F7F', hover: '#3A7399', active: '#1F4A66', subtle: '#1A3344' },
  font: {
    sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif",
    mono: "'SF Mono', 'Roboto Mono', Consolas, monospace",
    serif: "Georgia, 'Times New Roman', serif",
  },
  space: { xs: '4px', sm: '8px', md: '12px', lg: '16px', xl: '24px', xxl: '32px' },
  radius: { sm: '2px', md: '4px', lg: '8px', pill: '999px' },
  shadow: { focus: '0 0 0 2px #2C5F7F66', drill: '0 8px 24px rgba(0, 0, 0, 0.4)' },
} as const;

export type Tokens = typeof TOKENS;
