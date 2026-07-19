import { task } from "@trigger.dev/sdk/v3";
import { supabase } from "../lib/supabase";
import { classifyCompany } from "./classifyCompany";

// Entry point. Run this manually from the Trigger.dev dashboard or CLI.
// Selects all pending rows and fans them out to classifyCompany in parallel.
export const enrichBatch = task({
  id: "enrich-batch",
  run: async (_payload?: unknown) => {
    const batchSize = 1000;
    let totalDispatched = 0;

    while (true) {
      const { data: rows, error } = await supabase
        .from("master_companies")
        .select("id, domain, firmable_id")
        .eq("status", "pending")
        .limit(batchSize);

      if (error) throw new Error(`Failed to fetch pending rows: ${error.message}`);
      if (!rows || rows.length === 0) break;

      // Mark as 'processing' before dispatching to prevent double-processing on re-trigger
      const ids = rows.map((r) => r.id);
      await supabase.from("master_companies").update({ status: "processing" }).in("id", ids);

      await classifyCompany.batchTrigger(
        rows.map((r) => ({ payload: { companyId: r.id, firmableId: r.firmable_id ?? null } }))
      );

      totalDispatched += rows.length;
      if (rows.length < batchSize) break;
    }

    return { message: `Dispatched ${totalDispatched} companies for enrichment.`, processed: totalDispatched };
  },
});
