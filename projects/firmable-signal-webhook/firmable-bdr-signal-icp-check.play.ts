import { definePlay } from 'deepline';

type FirmableSignalEvent = {
  id: string;
  agent_id: number;
  agent_name: string;
  event_type: string;
  category: string;
  signal: string;
  signal_type_name: string;
  signal_type_slug: string;
  company_id: string | null;
  company_name: string | null;
  website: string | null;
  linkedin: string | null;
  source_url: string | null;
  summary: string | null;
  key_topics: string | null;
  person_id: string | null;
  person_name: string | null;
  agent_run_id: string | null;
  event_date: string | null;
  run_at: string | null;
  company_logo: string | null;
  social_post_summary: string | null;
  action_perform: unknown[];
};

type IcpVerdict = {
  tier: 'A' | 'B' | 'C' | 'D';
  score: number;
  reasons: string[];
  disqualified: boolean;
  disqualification_reason: string | null;
};

// icp-definition.md's scoring dimensions are company-level (sales team size,
// company type, sales function signals, competitive tech) — this is the same
// rubric .claude/skills/account-qualification/ uses. Do not add new criteria here.
const ICP_RUBRIC = `You score a company against Firmable's ICP rubric. Firmable targets companies with a genuine B2B outreach motion (selling products/services, sponsorships, donations, recruitment placements, or partnerships to other businesses).

Score each dimension independently, then sum for a total (max 90):

1. Sales Team Size (max 25): 20+ reps=25, 10-19=20, 5-9=15, 2-4=8, 1=3, 0/unknown=0.
2. Company Type / Industry (max 25): SaaS/Software=25, Recruitment/Staffing=20, Consulting/Professional Services=15, Financial Services=15, Events/Sponsorship Sales=15, Real Estate/PropTech=12, Non-profit with corporate fundraising=12, Other B2B=8, B2C/Consumer with no B2B revenue line=0, Unknown=0.
3. Sales Function Signals (max 20): SDR/BDR roles exist (job postings or headcount detected)=20, AE/Account Manager team=12, Recruitment consultants (BD-style role)=20, Founder-led sales only=5, none=0.
4. Competitive Tech Stack (max 20): ZoomInfo/Apollo.io/Lusha/Cognism detected=20, LinkedIn Sales Navigator only=10, none detected=0.

Tiers: 70+ = A, 40-69 = B, 20-39 = C, <20 = D (disqualified — do not contact).

The input you receive is a Firmable "company posted a new job" signal (already a Sales Function Signal — treat it as satisfying dimension 3 at the SDR/BDR level unless the job posting is clearly unrelated to sales/BD) plus, when available, Firmable company enrichment data (industries, employee_count, keywords, nextGen.technographics). If enrichment is missing, score conservatively on the fields you do have and say so in your reasons.

Return your reasons as short bullet-style strings citing which dimension drove the score.`;

function escapeSqlLiteral(value: string): string {
  // query_customer_db's statement-count guard flags any semicolon in the raw
  // SQL text, even one inside a quoted string literal, as a second statement.
  return value.replace(/'/g, "''").replace(/;/g, ',');
}

function sqlString(value: string | null): string {
  return value === null ? 'NULL' : `'${escapeSqlLiteral(value)}'`;
}

export default definePlay(
  'firmable-bdr-signal-icp-check',
  async (ctx, input: FirmableSignalEvent) => {
    if (input.category !== 'company' || input.signal_type_slug !== 'company-new-job-posted') {
      return {
        skipped: true,
        reason: `unsupported event: category=${input.category}, signal_type_slug=${input.signal_type_slug}`,
        firmable_event_id: input.id,
      };
    }

    let enrichment: Record<string, unknown> | null = null;
    let enrichmentStatus: 'enriched' | 'webhook_payload_only' | 'lookup_failed' = 'webhook_payload_only';

    if (input.company_id) {
      try {
        const lookup = await ctx.tools.execute({
          id: 'firmable_enrich',
          tool: 'firmable_company_lookup',
          input: { id: input.company_id },
          description: 'Enrich the signaled company before ICP scoring.',
        });
        enrichment = lookup.toolResponse.raw as Record<string, unknown>;
        enrichmentStatus = 'enriched';
      } catch (error) {
        enrichmentStatus = 'lookup_failed';
      }
    }

    const icpCheck = await ctx.tools.execute({
      id: 'icp_check',
      tool: 'ai_inference',
      input: {
        model: 'anthropic/claude-sonnet-4.6',
        system: ICP_RUBRIC,
        prompt: JSON.stringify({ signal: input, enrichment }),
        jsonSchema: {
          type: 'object',
          properties: {
            tier: { type: 'string', enum: ['A', 'B', 'C', 'D'] },
            score: { type: 'number' },
            reasons: { type: 'array', items: { type: 'string' } },
            disqualified: { type: 'boolean' },
            disqualification_reason: { type: ['string', 'null'] },
          },
          required: ['tier', 'score', 'reasons', 'disqualified', 'disqualification_reason'],
          additionalProperties: false,
        },
      },
      description: 'Score the signaled company against the Firmable ICP rubric.',
    });

    const verdict = (icpCheck.toolResponse.raw as unknown as { extracted_json: IcpVerdict })
      .extracted_json;

    const result = {
      firmable_event_id: input.id,
      company_id: input.company_id,
      company_name: input.company_name,
      signal_type: input.signal_type_slug,
      enrichment_status: enrichmentStatus,
      icp_tier: verdict.tier,
      icp_score: verdict.score,
      icp_reasons: verdict.reasons,
      disqualified: verdict.disqualified,
      disqualification_reason: verdict.disqualification_reason,
    };

    // query_customer_db has no parameterized-query option (sql is a single string),
    // so every value is escaped via sqlString()/escapeSqlLiteral() before interpolation.
    await ctx.tools.execute({
      id: 'persist_icp_check',
      tool: 'query_customer_db',
      input: {
        sql: `INSERT INTO analytics.firmable_signal_icp_checks
          (firmable_event_id, company_id, company_name, signal_type, enrichment_status,
           icp_tier, icp_score, icp_reasons, disqualified, disqualification_reason)
          VALUES (
            ${sqlString(result.firmable_event_id)},
            ${sqlString(result.company_id)},
            ${sqlString(result.company_name)},
            ${sqlString(result.signal_type)},
            ${sqlString(result.enrichment_status)},
            ${sqlString(result.icp_tier)},
            ${result.icp_score},
            ${sqlString(JSON.stringify(result.icp_reasons))},
            ${result.disqualified},
            ${sqlString(result.disqualification_reason)}
          )`,
      },
      description: 'Persist the ICP verdict for later querying/activation.',
    });

    return result;
  },
  {
    description: 'On a Firmable BDR/SDR job-posting signal, enrich the company and run an ICP fit check; log the verdict.',
    secrets: ['FIRMABLE_WEBHOOK_SECRET'],
    webhook: {
      hmac: {
        secretEnv: 'FIRMABLE_WEBHOOK_SECRET',
        header: 'x-firmable-signature',
        algorithm: 'sha256',
      },
    },
  },
);
