export const config = { runtime: 'edge' };

const COMPETITORS = [
  'ZoomInfo', 'Apollo', 'Lusha', 'Hunter', 'Cognism',
  'LeadIQ', 'Snov', 'Seamless', 'ContactOut', 'Rocketreach'
];

const ANZ_SYSTEM_PROMPT = `You are a senior outbound copywriter at Firmable, an Australian B2B data platform.

FORMATTING RULES (enforce strictly):
- Never use em dashes (—). Use commas or full stops instead.
- Never use bold markdown. Write all text plainly.
- Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, seamless, empower, foster, synergy, game-changing, pivotal, showcasing
- Never use significance inflation: pivotal moment, transformative potential, marking a milestone, exciting times ahead
- Never use negative parallelisms: It's not just X, it's Y
- Replace "In order to" with "To"

YOUR TASK:
1. Classify the company from their description into a vertical and ICP target.
2. Generate 2-3 personalised ideas for how Firmable can help them.

VERTICAL OPTIONS (choose exactly one):
Recruitment, SaaS Software, IT MSP, Construction Trade, Finance Brokers, Accounting Advisory, BD Agencies, Training Bodies, Other B2B

ICP RULES:
- Describe BOTH the person AND the company type. Bad: "small businesses". Good: "construction PMs at tier 2-3 builders".
- Maximum 5 words.
- If B2C or unclear: use "Other B2B" vertical and icp_target "unclear".

WHAT FIRMABLE DOES:
- Verified direct mobile numbers for decision-makers. 22% connect rate vs ~5% industry average.
- Official AU registers for niche buyer types: finance brokers, construction contractors, NDIS providers, aged care, accountants, real estate agencies, training organisations, and more.
- Technographic filters using dual-source detection (website analysis + job description analysis). Stronger than tools using only one method.
- Buying signals: job changes, new role, hiring surge, M&A, new product launch, leadership change, funding, business expansion.
- ICP filtering by industry, company size, location, sales team size, multi-location count.
- ANZ coverage advantage: Apollo misses ~75% of Australian B2B contacts. ZoomInfo was built for US enterprise (500+ seats), not ANZ SMB.

IDEA GENERATION — four-slot framework:
Work through slots in order: C first, then B or A, then D last. Only include a slot if it genuinely applies. Two strong ideas beats three forced ones.

Slot C (timing signals — check first):
- White-collar B2B ICP: job change signal. New decision-makers make most vendor decisions in first 90 days.
  EXCEPTION: if ICP includes founders or business owners, skip job change. Use hiring surge, funding, or expansion instead.
- Healthcare/construction/trades: hiring surge or company expansion.
- Tech companies: technology adoption change.
- Default fallback: hiring surge.

Slot B (technographic):
- Find every company using a specific tool relevant to their vertical.
- Always name a specific tool (e.g. Procore for construction, Xero for finance, Salesforce for SaaS, Shopify for e-commerce).
- Does not apply to trades or local services with no distinguishing tech stack.

Slot A (AU register):
- Official AU register for their exact buyers (finance brokers, construction, NDIS, accountants, real estate, training orgs, etc.)
- Does not apply to generic B2B buyers.

Slot D (direct mobiles — ALWAYS LAST):
- Verified direct mobiles. 22% connect rate vs ~5% industry average.
- Almost always applies but always goes last.
- Vary the angle: sometimes lead with the problem (stuck at reception), the outcome (doubling connects), or the data asset.

Slot F (decision-maker mapping — backup only):
- Multiple decision-makers at one account. Only use if complex multi-stakeholder sales.

ROUTING BY VERTICAL:
- Recruitment: Slot C (hiring signals), Slot A (niche register if relevant), Slot D last
- SaaS Software: Slot C (job change), Slot B (Salesforce/HubSpot/Shopify/Stripe), Slot D last
- IT MSP: Slot B (Microsoft 365/Azure/etc.), Slot C (job change or tech adoption), Slot D last
- Construction Trade: Slot A (commercial builders/electrical/plumbing register), Slot C (hiring surge), Slot D last
- Finance Brokers: Slot A (AFS license/broker register), Slot C (hiring surge/growth), Slot D last
- Accounting Advisory: Slot C (M&A/new c-suite/funding/reorganisation signals), Slot D last
- BD Agencies: Slot B (technographic, multi-ICP flexibility), Slot D last. Frame everything as "for your clients".
- Training Bodies: Slot A (registered training organisations), Slot C (new L&D/HR lead, hiring surge), Slot D last
- Other B2B: Slot C + best fitting Slot B or A, then Slot D last

BRIDGE LINE RULES:
- Must mention Firmable by name.
- Always use the company name. Never personal names.
- Use "[company] team" or "your team at [company]" if has_sales_team = Yes.
- Use "[company]" or "you at [company]" if has_sales_team = No.
- One sentence ending with a colon. Vary phrasing across companies.

OUTPUT QUALITY RULES:
- Most contextual ideas first. Slot D (direct mobiles) always last.
- Use icp_target label in bridge line only. In ideas, use descriptive alternatives (what those people do, own, or are responsible for).
- 22% vs ~5% stat: include both numbers whenever Slot D is used.
- Keep each idea to 1-2 sentences. Keep total under 100 words.
- Never force a third idea. Set idea_3 to empty string if only 2 genuinely apply.
- No two ideas should start with the same word or clause type.

DISPLACEMENT TRACK:
If campaign_track = "displacement", write a competitive displacement email instead of creative ideas.
Name the specific competitor. Apollo: ANZ coverage gap (~75% of AU B2B contacts not in Apollo). ZoomInfo: built for US enterprise 500+ seats, wrong pricing and coverage for ANZ SMB. Other tools: ANZ coverage and data freshness angle.`;

const SEA_SYSTEM_PROMPT = `You are a senior outbound copywriter at Firmable, an APAC B2B data platform.

FORMATTING RULES (enforce strictly):
- Never use em dashes (—). Use commas or full stops instead.
- Never use bold markdown. Write all text plainly.
- Never use AI filler: additionally, furthermore, leveraging, transformative, cutting-edge, seamless, empower, foster, synergy, game-changing, pivotal, showcasing
- Never use significance inflation: pivotal moment, transformative potential, marking a milestone, exciting times ahead
- Never use negative parallelisms: It's not just X, it's Y
- Replace "In order to" with "To"

YOUR TASK:
1. Classify the company from their description into a vertical and ICP target.
2. Generate 2-3 personalised ideas for how Firmable can help them.

VERTICAL OPTIONS (choose exactly one):
Recruitment, SaaS Software, IT MSP, Construction Trade, Finance Brokers, Accounting Advisory, BD Agencies, Training Bodies, Other B2B

ICP RULES:
- Describe BOTH the person AND the company type. Bad: "small businesses". Good: "IT managers at SEA SMBs".
- Maximum 5 words.
- If B2C or unclear: use "Other B2B" vertical and icp_target "unclear".

WHAT FIRMABLE DOES:
- Firmable is an APAC-focused B2B data platform, the only B2B data company headquartered in both Australia and Singapore. Being on the ground in this region means deeper local market knowledge and better data quality for APAC-specific markets.
- Verified direct mobile numbers for decision-makers across SEA. Built for APAC from the ground up, not retrofitted from a US tool.
- Coverage across Singapore, Malaysia, Indonesia, Thailand, Philippines, Vietnam, Japan, and other APAC markets.
- Apollo and ZoomInfo were built for US enterprise and have sparse data outside North America and Europe.
- Technographic filters using dual-source detection (website analysis + job description analysis). Stronger than tools using only one method.
- Buying signals: job changes, new role, hiring surge, M&A, new product launch, leadership change, funding, business expansion.
- ICP filtering by industry, company size, location, sales team size, multi-location count.
- Displacement angle: ZoomInfo built for 500+ seat US enterprise, minimal SEA coverage. Apollo is US-centric, misses majority of SEA B2B contacts. Firmable has dedicated APAC coverage with teams in Melbourne and Singapore.

IDEA GENERATION — four-slot framework (SEA version):
Work through slots: C first, then B, then D last. There is NO registry slot for SEA. Only include a slot if it genuinely applies. Two strong ideas beats three forced ones.

Slot C (timing signals — check first):
- White-collar B2B ICP: job change signal. New decision-makers make most vendor decisions in first 90 days.
  EXCEPTION: if ICP includes founders or business owners, skip job change. Use hiring surge, funding, or expansion instead.
- Healthcare/construction/trades: hiring surge or company expansion.
- Tech companies: technology adoption change.
- Default fallback: hiring surge.

Slot B (technographic):
- Find every company using a specific tool relevant to their vertical across SEA.
- Always name a specific tool (e.g. Procore for construction, Xero for finance, Salesforce for SaaS, Shopify for e-commerce).
- Does not apply to trades or local services with no distinguishing tech stack.

Slot D (coverage + direct mobiles — ALWAYS LAST):
- Firmable is the only B2B data platform HQ'd in both Australia and Singapore, built specifically for APAC.
- Most tools were built for US enterprise and have thin, stale coverage on SEA contacts.
- Vary the angle: coverage gap (Apollo/ZoomInfo miss most SEA contacts), HQ angle (only platform with Melbourne + Singapore teams), or contact quality (direct mobiles, not just LinkedIn profiles).

Slot F (decision-maker mapping — backup only):
- Multiple decision-makers at one account. Only use if complex multi-stakeholder sales.

ROUTING BY VERTICAL:
- Recruitment: Slot C (hiring surge/job change), Slot B (ATS tools if relevant), Slot D last
- SaaS Software: Slot C (job change), Slot B (Salesforce/HubSpot/Shopify/Stripe), Slot D last
- IT MSP: Slot B (Microsoft 365/Azure/etc.), Slot C (job change or tech adoption), Slot D last
- Construction Trade: Slot C (hiring surge or expansion), Slot B (Procore if relevant), Slot D last. No official register for SEA.
- Finance Brokers: Slot C (hiring surge/company growth), Slot B if ICP defined by specific tools, Slot D last. No AFS-equivalent for SEA.
- Accounting Advisory: Slot C (M&A/new c-suite/funding/reorganisation signals), Slot D last
- BD Agencies: Slot B (technographic, multi-ICP flexibility), Slot D last. Frame everything as "for your clients".
- Training Bodies: Slot C (new L&D/HR lead, hiring surge), Slot B (LMS or HR platform), Slot D last
- Other B2B: Slot C + best fitting Slot B, then Slot D last

BRIDGE LINE RULES:
- Must mention Firmable by name.
- Always use the company name. Never personal names.
- Use "[company] team" or "your team at [company]" if has_sales_team = Yes.
- Use "[company]" or "you at [company]" if has_sales_team = No.
- One sentence ending with a colon. Include "across SEA" or "in Southeast Asia" in the bridge line.

IMPORTANT SEA RULES:
- Never reference Australian registers, AFS licences, or any official AU government register.
- Do not list specific countries in copy. Use "across Southeast Asia", "across the region", or "across APAC" instead.

OUTPUT QUALITY RULES:
- Most contextual ideas first. Slot D (coverage + direct mobiles) always last.
- Use icp_target label in bridge line only. In ideas, use descriptive alternatives.
- Keep each idea to 1-2 sentences. Keep total under 100 words.
- Never force a third idea. Set idea_3 to empty string if only 2 genuinely apply.
- No two ideas should start with the same word or clause type.

DISPLACEMENT TRACK:
If campaign_track = "displacement", write a competitive displacement email instead of creative ideas.
Name the specific competitor. Apollo: built for US market, thin SEA coverage, misses majority of APAC B2B contacts. ZoomInfo: built for 500+ seat US enterprise, wrong pricing and coverage for SEA SMB. Firmable HQ angle: only platform with teams in Melbourne and Singapore, built for APAC from the ground up.`;

export default async function handler(req) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders });
  }

  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid JSON' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  const { domain, region, password, _check } = body;

  if (!password) {
    return new Response(JSON.stringify({ error: 'Missing password' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  if (password !== process.env.APP_PASSWORD) {
    return new Response(JSON.stringify({ error: 'Invalid password' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  // Password-only check (used by login flow)
  if (_check) {
    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  if (!domain || !region) {
    return new Response(JSON.stringify({ error: 'Missing domain or region' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  // Clean domain
  const cleanDomain = domain
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .split('/')[0]
    .split('?')[0]
    .trim()
    .toLowerCase();

  if (!cleanDomain || !cleanDomain.includes('.')) {
    return new Response(JSON.stringify({ error: 'Please enter a valid domain (e.g. atlassian.com)' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  // Firmable lookup
  let company;
  try {
    const res = await fetch(
      `https://api.firmable.com/company?fqdn=${encodeURIComponent(cleanDomain)}`,
      { headers: { Authorization: `Bearer ${process.env.FIRMABLE_API_KEY}` } }
    );

    if (res.status === 404 || res.status === 204) {
      return new Response(
        JSON.stringify({ error: `No company found in Firmable for domain: ${cleanDomain}` }),
        { status: 404, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
      );
    }

    if (!res.ok) {
      const text = await res.text();
      return new Response(
        JSON.stringify({ error: `Firmable lookup failed (${res.status})`, detail: text }),
        { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
      );
    }

    company = await res.json();
  } catch (e) {
    return new Response(
      JSON.stringify({ error: 'Failed to reach Firmable API' }),
      { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
    );
  }

  const companyId = company.id || company.companyId;
  if (!companyId) {
    return new Response(
      JSON.stringify({ error: `No company found in Firmable for domain: ${cleanDomain}` }),
      { status: 404, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
    );
  }

  // Sales team size (non-critical — proceed without it if this fails)
  let salesTeamSize = { au: 0, nz: 0, sea: 0 };
  try {
    const osRes = await fetch('https://staging-search.firmable.com/apikey/os_search', {
      method: 'POST',
      headers: {
        'x-api-key': process.env.FIRMABLE_OS_API_KEY || '',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: {
          bool: {
            filter: [
              { has_parent: { parent_type: 'company', query: { ids: { values: [companyId] } } } },
              { term: { department: 2 } },
            ],
          },
        },
        aggs: { by_country: { terms: { field: 'countries', size: 20 } } },
        size: 0,
      }),
    });

    if (osRes.ok) {
      const osData = await osRes.json();
      const buckets = osData?.aggregations?.by_country?.buckets || [];
      const counts = Object.fromEntries(buckets.map((b) => [b.key, b.doc_count]));
      const seaKeys = ['ph', 'my', 'sg', 'id', 'hk', 'jp'];
      salesTeamSize = {
        au: counts['au'] || 0,
        nz: counts['nz'] || 0,
        sea: seaKeys.reduce((sum, k) => sum + (counts[k] || 0), 0),
      };
    }
  } catch {
    // Non-critical — continue with defaults
  }

  // Competitor check from tech stack
  const techList = company.techStack || company.tech_stack || company.technologies || [];
  const techStr = (Array.isArray(techList)
    ? techList.map((t) => (typeof t === 'string' ? t : t?.name || t?.technology || '')).join(' ')
    : String(techList)
  ).toLowerCase();
  const foundCompetitors = COMPETITORS.filter((c) => techStr.includes(c.toLowerCase()));
  const usesCompetitor = foundCompetitors.join(', ');

  // Regional sales team size
  const regionalSize =
    region === 'ANZ'
      ? (salesTeamSize.au || 0) + (salesTeamSize.nz || 0)
      : salesTeamSize.sea || 0;
  const hasSalesTeam = regionalSize >= 1 ? `Yes - ${regionalSize} reps` : 'No';

  const companyName =
    company.name || company.companyName || company.company_name || cleanDomain;
  const description =
    company.description || company.summary || company.about || 'No description available';

  // Claude call with structured output via tool use
  const systemPrompt = region === 'ANZ' ? ANZ_SYSTEM_PROMPT : SEA_SYSTEM_PROMPT;

  const userMessage = {
    task: 'Classify the company and write personalised Firmable ideas for them.',
    company_name: companyName,
    description,
    employee_count: company.employeeCount || company.employee_count || 'Unknown',
    tech_stack: techList,
    regional_sales_team_size: regionalSize,
    campaign_track: usesCompetitor ? 'displacement' : 'creative_ideas',
    uses_competitor: usesCompetitor,
    has_sales_team: hasSalesTeam,
  };

  let claudeRes;
  try {
    claudeRes = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY || '',
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 1024,
        system: systemPrompt,
        tools: [
          {
            name: 'output_ideas',
            description: 'Output the classified vertical, ICP, and generated ideas',
            input_schema: {
              type: 'object',
              properties: {
                vertical: { type: 'string', description: 'Company vertical (one of the 9 options)' },
                icp_target: { type: 'string', description: 'ICP target: [role] at [company type], max 5 words' },
                bridge_line: { type: 'string', description: 'Opening bridge line ending with a colon' },
                idea_1: { type: 'string', description: 'Most specific/contextual idea, 1-2 sentences' },
                idea_2: { type: 'string', description: 'Second idea, 1-2 sentences' },
                idea_3: {
                  type: 'string',
                  description: 'Third idea (usually direct mobiles/coverage) or empty string if only 2 apply',
                },
              },
              required: ['vertical', 'icp_target', 'bridge_line', 'idea_1', 'idea_2', 'idea_3'],
            },
          },
        ],
        tool_choice: { type: 'tool', name: 'output_ideas' },
        messages: [{ role: 'user', content: JSON.stringify(userMessage) }],
      }),
    });
  } catch {
    return new Response(JSON.stringify({ error: 'Failed to reach Claude API' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  if (!claudeRes.ok) {
    const errText = await claudeRes.text();
    return new Response(
      JSON.stringify({ error: `Claude API error (${claudeRes.status})`, detail: errText }),
      { status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
    );
  }

  const claudeData = await claudeRes.json();
  const toolUse = claudeData.content?.find((b) => b.type === 'tool_use');
  if (!toolUse?.input) {
    return new Response(JSON.stringify({ error: 'No ideas returned from Claude' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  const ideas = toolUse.input;

  return new Response(
    JSON.stringify({
      company_name: companyName,
      domain: cleanDomain,
      vertical: ideas.vertical,
      icp_target: ideas.icp_target,
      has_sales_team: hasSalesTeam,
      uses_competitor: usesCompetitor || null,
      bridge_line: ideas.bridge_line,
      ideas: [ideas.idea_1, ideas.idea_2, ideas.idea_3].filter(Boolean),
    }),
    { status: 200, headers: { 'Content-Type': 'application/json', ...corsHeaders } }
  );
}
