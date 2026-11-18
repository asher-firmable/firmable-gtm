import { definePlay } from 'deepline';

// Minimal isolation test: does the webhook + HMAC secret handshake work at
// all, independent of everything the real firmable-bdr-signal-icp-check play
// does (enrichment, ai_inference, customer_db persistence)? This play does
// nothing but echo back whatever payload it receives.
export default definePlay(
  'firmable-webhook-echo-test',
  async (ctx, input: Record<string, unknown>) => {
    return {
      received: true,
      input,
    };
  },
  {
    description: 'Debug play: echoes back whatever payload it receives via webhook. No HMAC — security relies on the unguessable webhook URL token alone.',
    webhook: {},
  },
);
