import Anthropic from "npm:@anthropic-ai/sdk";
import { createClient } from "npm:@supabase/supabase-js";

const anthropic = new Anthropic({ apiKey: Deno.env.get("ANTHROPIC_API_KEY")! });
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

const SYSTEM_PROMPT = `You are a B2B sales intelligence analyst specialising in compliance and regtech markets in Australia. Your job is to evaluate company descriptions and determine whether a company sells tools or services that would help law firms, accountants, conveyancers, real estate agencies, or precious metal dealers meet their new AML/CTF obligations under AUSTRAC's Tranche 2 reforms (effective 1 July 2026).`;

function buildPrompt(description: string): string {
  return JSON.stringify({
    role: "B2B sales intelligence analyst — compliance and regtech markets",
    goal: "Determine whether the company described sells compliance software, regtech, AML or KYC tools, identity verification, legal/regulatory information, or fraud prevention services that would help the ~80,000 Australian firms newly regulated under AUSTRAC Tranche 2 meet their obligations.",
    task_steps_to_perform: [
      `1. Read the company description: ${description}`,
      "2. Decide if this is a vendor *selling into* the compliance/AML/KYC/identity/regtech space — not a company that is itself regulated (e.g. a bank, a law firm) or a generic tech company with no compliance angle",
      "3. Set result to true only if the description clearly mentions compliance, AML, KYC, identity verification, fraud prevention, legal/regulatory information, or risk management as a core offering",
      "4. Set result to false if the description is clearly unrelated, or if the company appears to be a buyer of compliance tools rather than a seller",
      "5. Set needs_web_check to true if the description is too short, too generic, or too vague to make a confident call",
      "6. Write a one-sentence reason referencing specific language from the description",
    ],
    constraints: [
      `Base your determination only on the description above — do not use any outside knowledge`,
      "Do not mark result true because a company sounds large or well-known — the description must explicitly confirm the compliance or AML angle",
      "needs_web_check is only true when result is false but uncertain — if result is true you are already confident and needs_web_check must be false",
      "If the description is fewer than 20 words or contains no product or service information, set result to false and needs_web_check to true",
      "Generic phrases like 'helping businesses grow', 'transforming industries', or 'enterprise software' alone are not enough to set result to true",
    ],
    output_format: "Respond with valid JSON only, no markdown, no explanation outside the JSON object.",
  });
}

async function processDescriptions(): Promise<void> {
  let processed = 0;

  while (true) {
    // Fetch a batch of pending rows
    const { data: rows, error } = await supabase
      .from("aml_companies")
      .select("id, description")
      .eq("status", "pending")
      .limit(50);

    if (error) {
      console.error("Fetch error:", error.message);
      break;
    }
    if (!rows || rows.length === 0) break;

    // Claim the batch immediately to prevent double-processing
    await supabase
      .from("aml_companies")
      .update({ status: "processing" })
      .in("id", rows.map((r) => r.id));

    for (const row of rows) {
      try {
        const description = row.description?.trim() || "";

        const msg = await anthropic.messages.create({
          model: "claude-haiku-4-5-20251001",
          max_tokens: 256,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: buildPrompt(description) }],
        });

        const rawText = (msg.content[0] as { type: string; text: string }).text;
        const raw = rawText.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/i, "").trim();
        const { result, reason, needs_web_check } = JSON.parse(raw);

        await supabase
          .from("aml_companies")
          .update({
            aml_result: result,
            aml_reason: reason,
            needs_web_check: needs_web_check,
            status: needs_web_check ? "pending_web" : "done",
          })
          .eq("id", row.id);

        processed++;
      } catch (e) {
        console.error(`Error on row ${row.id}:`, e);
        await supabase
          .from("aml_companies")
          .update({ status: "error", error_msg: String(e) })
          .eq("id", row.id);
      }
    }

    console.log(`Processed ${processed} rows so far...`);
  }

  console.log(`Done. Total processed: ${processed}`);
}

Deno.serve(async () => {
  // Detach processing from the HTTP response — returns 202 immediately
  EdgeRuntime.waitUntil(processDescriptions());

  return new Response(
    JSON.stringify({ started: true, message: "check-description running in background" }),
    { status: 202, headers: { "Content-Type": "application/json" } }
  );
});
