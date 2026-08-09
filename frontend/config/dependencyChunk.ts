const reactRuntimeDependencyPattern =
  /[\\/]node_modules[\\/](react-router-dom|react-router|react-dom|react|scheduler)[\\/]/;

export const getReactRuntimeChunk = (id: string): 'vendor-react' | undefined =>
  reactRuntimeDependencyPattern.test(id) ? 'vendor-react' : undefined;
