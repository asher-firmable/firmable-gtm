import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// Retry with exponential backoff for 429 rate limit errors
async function withRetry<T>(fn: () => Promise<T>, maxAttempts = 4): Promise<T> {
  let delay = 2000;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err: any) {
      const is429 = err?.status === 429 || err?.message?.includes("rate_limit");
      if (is429 && attempt < maxAttempts) {
        await new Promise((res) => setTimeout(res, delay));
        delay *= 2;
        continue;
      }
      throw err;
    }
  }
  throw new Error("unreachable");
}

// Prompt caching: the system prompt is cached after the first call.
// Subsequent calls in the same batch pay ~10% of normal input token cost.
export async function callClaude(
  systemPrompt: string,
  userMessage: string,
  model: string = "claude-haiku-4-5-20251001"
): Promise<string> {
  return withRetry(async () => {
    const response = await client.messages.create({
      model,
      max_tokens: 512,
      system: [
        {
          type: "text",
          text: systemPrompt,
          cache_control: { type: "ephemeral" },
        },
      ],
      messages: [{ role: "user", content: userMessage }],
    });
    return (response.content[0] as { text: string }).text.trim();
  });
}
