// Only React's rules of hooks: a hook placed after an early return blanked the whole Settings page in v1.3.22.
// `npm run build` runs this first, so that mistake can't ship again.
import hooks from 'eslint-plugin-react-hooks'

export default [{
  files: ['src/**/*.{js,jsx}'],
  languageOptions: { ecmaVersion: 'latest', sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
  plugins: { 'react-hooks': hooks },
  rules: { 'react-hooks/rules-of-hooks': 'error' },
}]
