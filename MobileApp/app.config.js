// Dynamic Expo config: injects the Google Maps API key from the environment so it is
// never committed to the repo. Set EXPO_PUBLIC_GOOGLE_MAPS_API_KEY in MobileApp/.env
// for local dev, and as an EAS environment variable for builds/updates.
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
