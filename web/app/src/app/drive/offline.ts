/**
 * ADR-024: what to say when a prebuilt grid can't be fetched.
 *
 * Offline, a grid the service worker has never cached fails to fetch (measured in Chrome with
 * @angular/service-worker 22.1.7: net::ERR_FAILED, so `fetch` throws; a 504 is also
 * possible from it), which read as "Failed to fetch" or "no prebuilt grid (HTTP 504)": no
 * help. A grid is kept for offline use once its engine has been started online.
 *
 * `status`: the HTTP status, or undefined when the fetch itself failed.
 * `online`: `navigator.onLine`, which can say true on a network that goes nowhere, so a
 * failed fetch while "online" still names the network.
 */
export function gridFetchError(preset: string, status: number | undefined, online: boolean): string {
  if (!online || status === undefined || status === 504) {
    return "This engine isn't on this device yet: start it once while online, and it works offline after that."
      + (status === undefined ? '' : ` (HTTP ${status})`);
  }
  return `no prebuilt grid for ${preset} (HTTP ${status})`;
}
