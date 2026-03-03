/**
 * Shared frontend constants.
 * BACKEND_URL is used by useSSEConsumer and useVoice hooks.
 */
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";
