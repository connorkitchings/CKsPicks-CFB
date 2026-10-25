import { cache } from "react";

/**
 * One clock reading per server request. React's `cache()` memoizes per request, so every
 * time-bucket computation in a request (release-cache loaders and the release pointer) sees
 * the same instant and a request never mixes buckets. Outside a React server request it
 * simply recomputes, which is fine for scripts; tests inject their own `now`.
 */
export const requestNow: () => number = cache(() => Date.now());
