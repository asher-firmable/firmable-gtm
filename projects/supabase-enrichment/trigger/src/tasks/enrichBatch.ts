import { task } from "@trigger.dev/sdk/v3";
import { supabase } from "../lib/supabase";
import { classifyCompany } from "./classifyCompany";

// Entry point. Run this manually from the Trigger.dev dashboard or CLI.
// Selects all pending rows and fans them out to classifyCompany in parallel.
export const enrichBatch = task({
  id: "enrich-batch",
  run: async (payload?: { limit?: number }) => {
    const limit = payload?.limit ?? 1000;

    const { data: rows, error } = await supabase
      .from("master_companies")
      .select("id, domain, firmable_id")
      .eq("status", "pending")
      .limit(limit);

    if (error) throw new Error(`Failed to fetch pending rows: ${error.message}`);
    if (!rows || rows.length === 0) {
      return { message: "No pending rows found.", processed: 0 };
    }

    // Mark all as 'processing' before dispatching to prevent double-processing
    const ids = rows.map((r) => r.id);
    await supabase.from("master_companies").update({ status: "processing" }).in("id", ids);

    // Fan out — Trigger.dev handles concurrency limits
    await classifyCompany.batchTrigger(
      rows.map((r) => ({ payload: { companyId: r.id, firmableId: r.firmable_id ?? null } }))
    );

    return { message: `Dispatched ${rows.length} companies for enrichment.`, processed: rows.length };
  },
});
