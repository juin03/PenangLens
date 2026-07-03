// Dynamic Expo config: injects the Google Maps API key from the environment so it is
// never committed to the repo. Set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY in MobileApp/.env
// for local dev, and as an EAS environment variable for builds/updates.
//
// This key is ONLY used by the native Maps SDK to render the home-tab map (free,
// unlimited on mobile). Places autocomplete goes through the backend proxy, so
// restrict this key to "Maps SDK for Android" (+ iOS) only — it is then worthless
// to anyone who extracts it from the app bundle.
const MAPS_KEY = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY || '';

export default ({ config }) => ({
  ...config,
  ios: {
    ...config.ios,
    config: {
      ...(config.ios?.config ?? {}),
      googleMapsApiKey: MAPS_KEY,
    },
  },
  android: {
    ...config.android,
    config: {
      ...(config.android?.config ?? {}),
      googleMaps: { apiKey: MAPS_KEY },
    },
  },
});
