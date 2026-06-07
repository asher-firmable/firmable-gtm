import { task } from "@trigger.dev/sdk/v3";
import { getCompany, supabase } from "../lib/supabase";
import { callClaude } from "../lib/claude";
import { scrapeWebsite } from "../lib/firecrawl";

// Classify the target persona: who does this company sell to?
// Adapted from scripts/enrich_persona_region.py:85-93
// Prompt is loaded from the PERSONA_PROMPT env var, populated from
// knowledge/target-persona-classification.md at deploy time.

const SYSTEM_PROMPT = process.env.PERSONA_PROMPT ?? `
You are a B2B sales analyst. Identify who the PRIMARY buyer or target customer is for this company.

Return the label as exactly two roles joined with "or", followed by a shared descriptor where it makes sense.
Format: "[Role1] or [Role2] [shared descriptor]"
All lowercase. 3-6 words total.

Rules:
- Always two roles joined with "or" — never one, never three
- Pick roles that are genuinely different but both realistic buyers
- Use the most specific titles that fit — avoid vague catch-alls like "business leaders"
- The shared descriptor (managers, leaders, directors, owners, operators, etc.) is optional if both roles already end in a title

Reply with a JSON object:
{"label": "<label>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}

Examples:
- "CFOs or operations managers"
- "IT or security leaders"
- "CMOs or marketing directors"
- "restaurant or hotel operators"
- "developers or project owners"
- "CIOs or IT managers"
- "HR or wellness managers"
- "shipowners or fleet managers"
- "bank or fintech leaders"
- "L&D or HR managers"
- "CISOs or AppSec managers"
- "manufacturing or operations directors"
- "telecom or network operators"
`.trim();

// Note: prompts are kept in sync with preview_prompts.py — update both together

const CONFIDENCE_THRESHOLD = 0.75;

export const classifyPersona = task({
  id: "classify-persona",
  concurrencyLimit: 3,
  retry: { maxAttempts: 3 },
  run: async ({ companyId }: { companyId: string }) => {
    try {
      const company = await getCompany(companyId);

      // Master table cache check
      if (company.target_persona) {
        await supabase.from("companies").update({ status: "done" }).eq("id", companyId);
        return { skipped: true, reason: "already classified" };
      }

      // Priority: Firmable/CSV description first, then Firecrawl cache
      let context = company.description?.trim() || company.website_summary || "";
      let result = await classify(context, company.domain);

      // Fall back to Firecrawl if confidence is low and we haven't scraped yet
      if (result.confidence < CONFIDENCE_THRESHOLD && !company.website_summary) {
        const scraped = await scrapeWebsite(company.domain);
        if (scraped) {
          context = scraped;
          result = await classify(context, company.domain);
          await supabase
            .from("companies")
            .update({ website_summary: scraped })
            .eq("id", companyId);
        }
      }

      await supabase
        .from("companies")
        .update({
          target_persona: result.label,
          persona_reasoning: result.reasoning,
          status: "done",
        })
        .eq("id", companyId);

      return { label: result.label, confidence: result.confidence };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await supabase.from("companies").update({ status: "error", error_msg: msg }).eq("id", companyId);
      throw err;
    }
  },
});

async function classify(
  context: string,
  domain: string
): Promise<{ label: string; confidence: number; reasoning: string }> {
  const userMsg = context
    ? `Company domain: ${domain}\n\nDescription:\n${context}`
    : `Company domain: ${domain}\n\n(No description available — infer from domain name if possible.)`;

  const raw = await callClaude(SYSTEM_PROMPT, userMsg);

  try {
    const cleaned = raw.replace(/```json\n?|```/g, "").trim();
    return JSON.parse(cleaned);
  } catch {
    return { label: "Unknown", confidence: 0.5, reasoning: raw.slice(0, 200) };
  }
}
