import { polyfillGlobal } from "react-native/Libraries/Utilities/PolyfillFunctions";
import { ReadableStream } from "web-streams-polyfill";
import { fetch, Headers, Request, Response } from "react-native-fetch-api";

polyfillGlobal("ReadableStream", () => ReadableStream);
polyfillGlobal(
  "fetch",
  () =>
    (...args) =>
      fetch(args[0], { ...args[1], reactNative: { textStreaming: true } }),
);
polyfillGlobal("Headers", () => Headers);
polyfillGlobal("Request", () => Request);
polyfillGlobal("Response", () => Response);

import "expo-router/entry";
