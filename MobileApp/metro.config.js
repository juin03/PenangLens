const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// Allow Metro to resolve files outside MobileApp folder
config.watchFolders = [
  path.resolve(__dirname, '..'), // Parent directory (PenangLens)
];

// Resolve modules from parent directory
config.resolver.nodeModulesPaths = [
  path.resolve(__dirname, 'node_modules'),
];

module.exports = config;
