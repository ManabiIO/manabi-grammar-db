import commonjs from '@rollup/plugin-commonjs';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import { terser } from 'rollup-plugin-terser';

export default {
  input: 'src/client.js',
  output: {
    file: 'dist/index.js',
    format: 'esm',
    sourcemap: true
  },
  external: ['./sqlite3-node.mjs', './sqlite3.mjs', 'node:fs/promises'],
  plugins: [
    nodeResolve({ preferBuiltins: true }),
    commonjs(),
    terser()
  ]
};
