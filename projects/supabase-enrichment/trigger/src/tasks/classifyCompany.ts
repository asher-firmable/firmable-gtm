import { task } from "@trigger.dev/sdk/v3";
import { getCompany, supabase } from "../lib/supabase";
import { callClaude } from "../lib/claude";
import { scrapeWebsite } from "../lib/firecrawl";
import { fetchFirmableDescription } from "../lib/firmable";
import { classifyPersona } from "./classifyPersona";

// Classify a company's type: SaaS/Software | MSP | IT Services | Other B2B
// Prompt is loaded from the COMPANY_TYPE_PROMPT env var, which is populated from
// knowledge/company-type-classification.md at deploy time.
// If confidence is low, falls back to Firecrawl before a second attempt.

const SYSTEM_PROMPT = process.env.COMPANY_TYPE_PROMPT ?? `
You are a B2B company classifier. Classify the company into exactly one of these five types:

- SaaS/Software providers: sells a software product on a subscription or license basis
- MSPs: managed service provider; manages IT infrastructure or cloud environments for clients on an ongoing basis
- IT services firms: IT consulting, staffing, implementation, or support services (people and expertise, not a product)
- IT Solutions providers: sells technology solutions that combine hardware and/or software into a packaged system (e.g. control room systems, networking hardware, industrial tech, AV/surveillance, purpose-built devices); may also offer related services
- Other B2B companies: any other B2B business that doesn't fit the above (e.g. pure hardware manufacturing, robotics integrators, engineering firms, staffing outside IT)

Key distinctions:
- If the company's core offering is a deployable technology system (hardware+software together), use IT Solutions providers — not SaaS/Software providers or Other B2B companies
- If the company makes or integrates physical machinery/robotics with no software product, use Other B2B companies
- MSPs vs IT services firms: MSPs implies ongoing managed contracts; IT services firms implies project-based consulting or implementation
- Pure IT staffing and recruiting firms (no consulting, no implementation — just placing candidates or contractors) go to Other B2B companies, not IT services firms

Reply with a JSON object: {"label": "<one of the five types>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}
`.trim();

// Note: prompts are kept in sync with preview_prompts.py — update both together

const CONFIDENCE_THRESHOLD = 0.75;

export const classifyCompany = task({
  id: "classify-company",
  concurrencyLimit: 3,
  retry: { maxAttempts: 3 },
  run: async ({ companyId, firmableId }: { companyId: string; firmableId?: string | null }) => {
    try {
      const company = await getCompany(companyId);

      // Master table cache check: skip if already classified
      if (company.company_type) {
        await classifyPersona.trigger({ companyId });
        return { skipped: true, reason: "already classified" };
      }

      // Priority 1: Firmable API description
      let context = "";
      if (firmableId) {
        const firmableDesc = await fetchFirmableDescription(firmableId);
        if (firmableDesc) {
          context = firmableDesc;
          await supabase.from("companies").update({ description: firmableDesc }).eq("id", companyId);
        }
      }

      // Priority 2: description from CSV upload
      if (!context && company.description?.trim()) {
        context = company.description.trim();
      }

      // First attempt
      let result = await classify(context, company.domain);

      // If confidence is low, fall back to Firecrawl (but only once)
      if (result.confidence < CONFIDENCE_THRESHOLD && !company.website_summary) {
        const scraped = await scrapeWebsite(company.domain);
        if (scraped) {
          context = scraped;
          result = await classify(context, company.domain);
          await supabase.from("companies").update({ website_summary: scraped }).eq("id", companyId);
        }
      }

      await supabase
        .from("companies")
        .update({
          company_type: result.label,
          company_type_reasoning: result.reasoning,
        })
        .eq("id", companyId);

      // Chain to Agent 2
      await classifyPersona.trigger({ companyId });

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
    : `Company domain: ${domain}\n\n(No description available — classify based on domain name if possible.)`;

  const raw = await callClaude(SYSTEM_PROMPT, userMsg);

  try {
    // Strip markdown fences if Claude wraps the JSON
    const cleaned = raw.replace(/```json\n?|```/g, "").trim();
    return JSON.parse(cleaned);
  } catch {
    // Fallback if Claude doesn't return valid JSON
    return { label: "Other B2B", confidence: 0.5, reasoning: raw.slice(0, 200) };
  }
}
