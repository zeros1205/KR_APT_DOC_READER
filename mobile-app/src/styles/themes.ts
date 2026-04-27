export const THEMES = {
  A: {
    primary: '#d97757',
    primaryDark: '#b85c38',
    primaryLight: '#fdf0ea',
    accent: '#6a9bcc',
    bg: '#faf9f5',
    surface: '#ffffff',
    dark: '#2c2925',
    mid: '#767370',
    lightGray: '#e8e6dc',
  },
  B: {
    primary: '#386641',
    primaryDark: '#2f5236',
    accent: '#6a994e',
    bg: '#f2e8cf',
    surface: '#ffffff',
    dark: '#2c2925',
    mid: '#6a994e',
    lightGray: 'rgba(56,102,65,0.20)',
  },
  C: {
    primary: '#ffafcc',
    primaryDark: '#cc7fa0',
    accent: '#a2d2ff',
    bg: '#fdf8ff',
    surface: '#ffffff',
    dark: '#2d1f3d',
    mid: '#8070a0',
    lightGray: '#ddd0f0',
  },
};

export type ThemePalette = keyof typeof THEMES;

export const getTheme = (palette: ThemePalette) => THEMES[palette];
