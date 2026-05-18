import type { Preview } from '@storybook/html';
import { withThemeByClassName } from '@storybook/addon-themes';

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#fafafa' },
        { name: 'dark', value: '#171717' },
      ],
    },
    options: {
      storySort: {
        order: ['Welcome', 'Foundation', ['Colors', 'Typography', 'Spacing', 'Radius', 'Shadow', 'Motion'], 'Components'],
      },
    },
  },
  decorators: [
    withThemeByClassName({
      themes: {
        light: 'theme-light',
        dark: 'theme-dark',
      },
      defaultTheme: 'light',
    }),
  ],
  tags: ['autodocs'],
};

export default preview;
