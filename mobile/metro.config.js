// Metro bundler config for the Dragonfly Expo app.
//
// `unstable_enablePackageExports` is required so Metro honours the
// "exports" map in package.json -- without it `@azure/msal-browser`
// fails to resolve `@azure/msal-common/browser` at bundle time (Metro
// falls back to "main" instead of "exports.browser.import").
//
// Safe to keep on at the project level: the rest of the dep graph
// either uses no exports map or has a working "default" fallback.

const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
config.resolver.unstable_enablePackageExports = true;

module.exports = config;
