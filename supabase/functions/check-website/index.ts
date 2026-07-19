import Anthropic from "npm:@anthropic-ai/sdk";
import { createClient } from "npm:@supabase/supabase-js";

const anthropic = new Anthropic({ apiKey: Deno.env.get("ANTHROPIC_API_KEY")! });
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

const SYSTEM_PROMPT = `You are a B2B sales intelligence analyst specialising in compliance and regtech markets in Australia. Your job is to evaluate company websites and determine whether a company sells tools or services that would help law firms, accountants, conveyancers, real estate agencies, or precious metal dealers meet their new AML/CTF obligations under AUSTRAC's Tranche 2 reforms (effective 1 July 2026).`;

function extractText(html: string): string {
  // Remove script/style blocks
  let text = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&#\d+;/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
  // Cap at 3000 chars — homepage above-the-fold is enough
  return text.slice(0, 3000);
}

function buildPrompt(domain: string, pageText: string): string {
  return JSON.stringify({
    role: "B2B sales intelligence analyst — compliance and regtech markets",
    goal: "Determine whether this company sells compliance software, regtech, AML or KYC tools, identity verification, legal/regulatory information, or fraud prevention services that would help the ~80,000 Australian firms newly regulated under AUSTRAC Tranche 2 meet their obligations.",
    website: domain,
    page_content: pageText,
    task_steps_to_perform: [
      "1. Read the page content above carefully",
      "2. Decide if this is a vendor *selling into* the compliance/AML/KYC/identity/regtech space — not a company that is itself regulated (e.g. a bank, a law firm) or a generic tech company with no compliance angle",
      "3. Set result to true only if the page content clearly mentions compliance, AML, KYC, identity verification, fraud prevention, legal/regulatory information, or risk management as a core offering",
      "4. Set result to false if the page content is clearly unrelated, or if the company appears to be a buyer of compliance tools rather than a seller",
      "5. Write a one-sentence reason referencing specific language from the page content",
    ],
    constraints: [
      "Base your determination only on the page content above — the description-level check was inconclusive, so weigh the website copy carefully",
      "Do not mark result true because a company sounds large or well-known — the page must explicitly confirm the compliance or AML angle",
      "If the page content is too short or clearly failed to load (e.g. only cookie banners or navigation), set result to false with reason explaining the page was inaccessible",
      "Generic phrases like 'helping businesses grow', 'transforming industries', or 'enterprise software' alone are not enough to set result to true",
    ],
    output_format: "Respond with valid JSON only, no markdown, no explanation outside the JSON object. Format: { \"result\": true|false, \"reason\": \"one sentence\" }",
  });
}

async function fetchPage(domain: string): Promise<string> {
  const urls = [`https://${domain}`, `http://${domain}`];
  for (const url of urls) {
    try {
      const res = await fetch(url, {
        signal: AbortSignal.timeout(10_000),
        headers: {
          "User-Agent":
            "Mozilla/5.0 (compatible; SalesBot/1.0; +https://firmable.com)",
        },
        redirect: "follow",
      });
      if (res.ok) {
        const html = await res.text();
        return extractText(html);
      }
    } catch {
      // try next URL
    }
  }
  return "";
}

async function processWebChecks(): Promise<void> {
  let processed = 0;

  while (true) {
    const { data: rows, error } = await supabase
      .from("aml_companies")
      .select("id, domain")
      .eq("status", "pending_web")
      .limit(20);

    if (error) {
      console.error("Fetch error:", error.message);
      break;
    }
    if (!rows || rows.length === 0) break;

    // Claim the batch
    await supabase
      .from("aml_companies")
      .update({ status: "processing" })
      .in("id", rows.map((r) => r.id));

    for (const row of rows) {
      try {
        const pageText = await fetchPage(row.domain);

        if (!pageText || pageText.length < 50) {
          await supabase
            .from("aml_companies")
            .update({
              web_result: false,
              web_reason: "Website inaccessible or returned no readable content.",
              status: "done",
            })
            .eq("id", row.id);
          processed++;
          continue;
        }

        const msg = await anthropic.messages.create({
          model: "claude-haiku-4-5-20251001",
          max_tokens: 256,
          system: SYSTEM_PROMPT,
          messages: [
            { role: "user", content: buildPrompt(row.domain, pageText) },
          ],
        });

        const rawText = (msg.content[0] as { type: string; text: string }).text;
        const raw = rawText.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/i, "").trim();
        const { result, reason } = JSON.parse(raw);

        await supabase
          .from("aml_companies")
          .update({
            web_result: result,
            web_reason: reason,
            status: "done",
          })
          .eq("id", row.id);

        processed++;
      } catch (e) {
        console.error(`Error on row ${row.id} (${row.domain}):`, e);
        await supabase
          .from("aml_companies")
          .update({ status: "error", error_msg: String(e) })
          .eq("id", row.id);
      }
    }

    console.log(`Processed ${processed} web checks so far...`);
  }

  console.log(`Done. Total web checks processed: ${processed}`);
}

Deno.serve(async () => {
  EdgeRuntime.waitUntil(processWebChecks());

  return new Response(
    JSON.stringify({
      started: true,
      message: "check-website running in background",
    }),
    { status: 202, headers: { "Content-Type": "application/json" } }
  );
});
