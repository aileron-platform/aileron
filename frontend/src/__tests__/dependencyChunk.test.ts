import { describe, expect, it } from 'vitest';

import { getReactRuntimeChunk } from '../../config/dependencyChunk';

describe('dependencyChunk', () => {
  it.each([
    '/app/node_modules/react/index.js',
    '/app/node_modules/react-dom/client.js',
    '/app/node_modules/react-router/dist/index.js',
    '/app/node_modules/react-router-dom/dist/index.js',
    '/app/node_modules/scheduler/index.js',
    'C:\\app\\node_modules\\react-router\\dist\\index.js',
  ])('keeps the React runtime graph in one chunk for %s', (id) => {
    expect(getReactRuntimeChunk(id)).toBe('vendor-react');
  });

  it('does not merge non-React dependencies into the React chunk', () => {
    expect(
      getReactRuntimeChunk('/app/node_modules/@remix-run/router/dist/router.js'),
    ).toBeUndefined();
  });
});
