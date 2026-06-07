import { createClient } from "@supabase/supabase-js";
import WS from "ws";

// Polyfill WebSocket for Node.js < 22 before any Supabase client init
if (!globalThis.WebSocket) {
  (globalThis as any).WebSocket = WS;
}

export const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export interface Company {
  id: string;
  domain: string;
  description: string | null;
  website_summary: string | null;
  company_type: string | null;
  company_type_reasoning: string | null;
  target_persona: string | null;
  persona_reasoning: string | null;
  status: string;
}

export async function getCompany(id: string): Promise<Company> {
  const { data, error } = await supabase
    .from("master_companies")
    .select("*")
    .eq("id", id)
    .single();
  if (error) throw new Error(`Supabase fetch failed for ${id}: ${error.message}`);
  return data as Company;
}
