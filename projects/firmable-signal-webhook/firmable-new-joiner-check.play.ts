import { definePlay } from 'deepline';

// Firmable's actual webhook body nests the event under `signal` (confirmed by
// sending a live "New joiner" signal.found event through the echo-test play)
// — unlike firmable-bdr-signal-icp-check.play.ts's FirmableSignalEvent, which
// assumes a flat shape. If that assumption is wrong for job-posting events
// too, that play is reading undefined fields; worth checking against a live
// payload the same way this one was.
type FirmableNewJoinerSignal = {
  id: string;
  category: string;
  signal: string;
  signal_type_name: string;
  signal_type_slug: string;
  company_id: string | null;
  company_name: string | null;
  person_id: string | null;
  person_name: string | null;
  website: string | null;
  linkedin: string | null;
  source_url: string | null;
  summary: string | null;
  key_topics: string | null;
  event_date: string | null;
  run_at: string | null;
  agent_run_id: string | null;
  company_logo: string | null;
  social_post_summary: string | null;
  surge_score: string | null;
  topic_name: string | null;
  action_perform: unknown[];
};

type FirmableWebhookEvent = {
  agent_id: number;
  agent_name: string;
  event_type: string;
  signal: FirmableNewJoinerSignal;
};

type HubSpotCompanyProps = {
  name?: string | null;
  domain?: string | null;
  firmable_id?: string | null;
  hubspot_owner_id?: string | null;
  ownername?: string | null;
  owneremail?: string | null;
  sdr__new_?: string | null;
  sdr_nz?: string | null;
  sdr_sea?: string | null;
  sdr_us?: string | null;
};

type HubSpotContactProps = {
  email?: string | null;
  firstname?: string | null;
  lastname?: string | null;
  hubspot_owner_id?: string | null;
  ownername?: string | null;
  owneremail?: string | null;
};

type HubSpotRecord<P> = { id: string; properties: P };

type HubSpotOwner = { id: string; email?: string; firstName?: string; lastName?: string };

// SDR fields are per-region select properties whose stored value is already
// the assigned rep's display name (unlike hubspot_owner_id, which is an owner
// ID requiring a lookup). Report the first region that's populated.
const SDR_FIELDS: Array<{ field: keyof HubSpotCompanyProps; label: string }> = [
  { field: 'sdr__new_', label: 'AU' },
  { field: 'sdr_nz', label: 'NZ' },
  { field: 'sdr_sea', label: 'SEA' },
  { field: 'sdr_us', label: 'US' },
];

const COMPANY_PROPERTIES = [
  'name', 'domain', 'firmable_id', 'hubspot_owner_id', 'ownername', 'owneremail',
  'sdr__new_', 'sdr_nz', 'sdr_sea', 'sdr_us',
];
const CONTACT_PROPERTIES = ['email', 'firstname', 'lastname', 'hubspot_owner_id', 'ownername', 'owneremail'];

function escapeSqlLiteral(value: string): string {
  // query_customer_db's statement-count guard flags any semicolon in the raw
  // SQL text, even one inside a quoted string literal, as a second statement.
  return value.replace(/'/g, "''").replace(/;/g, ',');
}

function sqlString(value: string | null | undefined): string {
  return value === null || value === undefined ? 'NULL' : `'${escapeSqlLiteral(value)}'`;
}

function sqlBool(value: boolean): string {
  return value ? 'TRUE' : 'FALSE';
}

function bareDomain(url: string): string {
  return url.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
}

function normalizeName(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, ' ');
}

export default definePlay(
  'firmable-new-joiner-check',
  async (ctx, input: FirmableWebhookEvent) => {
    const signal = input.signal;

    if (!signal || signal.category !== 'company' || signal.signal_type_slug !== 'company-new-joiner') {
      return {
        skipped: true,
        reason: `unsupported event: category=${signal?.category}, signal_type_slug=${signal?.signal_type_slug}`,
        firmable_event_id: signal?.id ?? null,
      };
    }

    // ── Company enrichment ────────────────────────────────────────────────
    let companyEnrichment: Record<string, unknown> | null = null;
    let companyEnrichmentStatus: 'enriched' | 'missing_id' | 'lookup_failed' = 'missing_id';

    if (signal.company_id) {
      try {
        const lookup = await ctx.tools.execute({
          id: 'firmable_company_enrich',
          tool: 'firmable_company_lookup',
          input: { id: signal.company_id },
          description: 'Enrich the signaled company.',
        });
        companyEnrichment = lookup.toolResponse.raw as Record<string, unknown>;
        companyEnrichmentStatus = 'enriched';
      } catch (error) {
        companyEnrichmentStatus = 'lookup_failed';
      }
    }

    // ── Person enrichment ────────────────────────────────────────────────
    let personEnrichment: Record<string, unknown> | null = null;
    let personEnrichmentStatus: 'enriched' | 'missing_id' | 'lookup_failed' = 'missing_id';

    if (signal.person_id) {
      try {
        const lookup = await ctx.tools.execute({
          id: 'firmable_person_enrich',
          tool: 'firmable_person_lookup',
          input: { id: signal.person_id },
          description: 'Enrich the new joiner.',
        });
        personEnrichment = lookup.toolResponse.raw as Record<string, unknown>;
        personEnrichmentStatus = 'enriched';
      } catch (error) {
        personEnrichmentStatus = 'lookup_failed';
      }
    }

    const companyDomainRaw =
      (companyEnrichment?.fqdn as string | undefined) ??
      (companyEnrichment?.website as string | undefined) ??
      null;
    const companyDomain = companyDomainRaw ? bareDomain(companyDomainRaw) : null;

    // ── HubSpot check: by domain ───────────────────────────────────────────
    let hubspotByDomain: HubSpotRecord<HubSpotCompanyProps> | null = null;
    if (companyDomain) {
      const result = await ctx.tools.execute({
        id: 'hubspot_check_domain',
        tool: 'hubspot_search_objects',
        input: {
          object_type: 'companies',
          properties: COMPANY_PROPERTIES,
          filter_groups: [{ filters: [{ propertyName: 'domain', operator: 'EQ', value: companyDomain }] }],
          limit: 1,
        },
        description: 'Check if the company exists in HubSpot by domain.',
      });
      const rows = (result.toolResponse.raw as { results?: Array<HubSpotRecord<HubSpotCompanyProps>> })?.results ?? [];
      hubspotByDomain = rows[0] ?? null;
    }

    // ── HubSpot check: by Firmable ID ──────────────────────────────────────
    let hubspotByFirmableId: HubSpotRecord<HubSpotCompanyProps> | null = null;
    if (signal.company_id) {
      const result = await ctx.tools.execute({
        id: 'hubspot_check_firmable_id',
        tool: 'hubspot_search_objects',
        input: {
          object_type: 'companies',
          properties: COMPANY_PROPERTIES,
          filter_groups: [{ filters: [{ propertyName: 'firmable_id', operator: 'EQ', value: signal.company_id }] }],
          limit: 1,
        },
        description: 'Check if the company exists in HubSpot by Firmable ID.',
      });
      const rows = (result.toolResponse.raw as { results?: Array<HubSpotRecord<HubSpotCompanyProps>> })?.results ?? [];
      hubspotByFirmableId = rows[0] ?? null;
    }

    const hubspotMatchByDomain = hubspotByDomain !== null;
    const hubspotMatchByFirmableId = hubspotByFirmableId !== null;
    const hubspotCompanyRecord = hubspotByFirmableId ?? hubspotByDomain;
    const hubspotRecordId = hubspotCompanyRecord?.id ?? null;

    // ── HubSpot check: does the new joiner exist as a contact? ─────────────
    // Firmable's person enrichment rarely includes a work email for very
    // recent joiners, so prefer an email match and fall back to matching by
    // name among contacts already associated with the matched company.
    const emails = personEnrichment?.emails as
      | { work?: Array<{ value: string }>; personal?: Array<{ value: string }> }
      | undefined;
    const personEmail = emails?.work?.[0]?.value ?? emails?.personal?.[0]?.value ?? null;

    let hubspotContactRecord: HubSpotRecord<HubSpotContactProps> | null = null;
    let personMatchMethod: 'email' | 'name_at_company' | 'not_checked' = 'not_checked';

    if (personEmail) {
      const result = await ctx.tools.execute({
        id: 'hubspot_check_contact_email',
        tool: 'hubspot_search_objects',
        input: {
          object_type: 'contacts',
          properties: CONTACT_PROPERTIES,
          filter_groups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: personEmail }] }],
          limit: 1,
        },
        description: 'Check if the new joiner exists in HubSpot by email.',
      });
      const rows = (result.toolResponse.raw as { results?: Array<HubSpotRecord<HubSpotContactProps>> })?.results ?? [];
      hubspotContactRecord = rows[0] ?? null;
      personMatchMethod = 'email';
    } else if (hubspotRecordId && signal.person_name) {
      const result = await ctx.tools.execute({
        id: 'hubspot_check_contact_by_company',
        tool: 'hubspot_search_objects',
        input: {
          object_type: 'contacts',
          properties: CONTACT_PROPERTIES,
          filter_groups: [{ filters: [{ propertyName: 'associatedcompanyid', operator: 'EQ', value: hubspotRecordId }] }],
          limit: 50,
        },
        description: 'List HubSpot contacts at the matched company to check for the new joiner by name (no email from Firmable).',
      });
      const rows = (result.toolResponse.raw as { results?: Array<HubSpotRecord<HubSpotContactProps>> })?.results ?? [];
      const targetName = normalizeName(signal.person_name);
      hubspotContactRecord =
        rows.find((r) => normalizeName(`${r.properties.firstname ?? ''} ${r.properties.lastname ?? ''}`) === targetName) ??
        null;
      personMatchMethod = 'name_at_company';
    }

    const personExistsInHubspot = hubspotContactRecord !== null;

    // ── Owner name resolution ───────────────────────────────────────────────
    // ownername/owneremail are pre-resolved rollup text fields but are often
    // null even when hubspot_owner_id is set, so fall back to a live owners
    // lookup only when a name still needs resolving.
    const companyOwnerId = hubspotCompanyRecord?.properties.hubspot_owner_id ?? null;
    const companyOwnerNameProp = hubspotCompanyRecord?.properties.ownername ?? null;
    const contactOwnerId = hubspotContactRecord?.properties.hubspot_owner_id ?? null;
    const contactOwnerNameProp = hubspotContactRecord?.properties.ownername ?? null;

    let ownerMap: Record<string, string> = {};
    if ((companyOwnerId && !companyOwnerNameProp) || (contactOwnerId && !contactOwnerNameProp)) {
      const ownersResult = await ctx.tools.execute({
        id: 'hubspot_resolve_owners',
        tool: 'hubspot_list_owners',
        input: { limit: 100 },
        description: 'Resolve owner IDs to names for the summary.',
      });
      const owners = (ownersResult.toolResponse.raw as { results?: HubSpotOwner[] })?.results ?? [];
      ownerMap = Object.fromEntries(
        owners.map((o) => [o.id, `${o.firstName ?? ''} ${o.lastName ?? ''}`.trim() || o.email || o.id]),
      );
    }

    const companyOwner = companyOwnerNameProp ?? (companyOwnerId ? ownerMap[companyOwnerId] ?? companyOwnerId : null);
    const contactOwner = contactOwnerNameProp ?? (contactOwnerId ? ownerMap[contactOwnerId] ?? contactOwnerId : null);

    const companySdr =
      SDR_FIELDS.map(({ field, label }) => {
        const value = hubspotCompanyRecord?.properties[field];
        return value ? `${value} (${label})` : null;
      }).find((v) => v !== null) ?? null;

    // ── Last step: quick human-readable summary ─────────────────────────────
    const summaryLines = [
      `Company "${signal.company_name ?? signal.company_id}" in HubSpot: ${hubspotCompanyRecord ? 'YES' : 'NO'}` +
        (hubspotCompanyRecord ? ` (owner: ${companyOwner ?? '(none)'}, SDR: ${companySdr ?? '(none)'})` : ''),
      `Person "${signal.person_name ?? signal.person_id}" in HubSpot: ${personExistsInHubspot ? 'YES' : 'NO'}` +
        (personExistsInHubspot
          ? ` (owner: ${contactOwner ?? '(none)'}, matched by ${personMatchMethod})`
          : personMatchMethod === 'not_checked'
            ? ' (not checked — no email from Firmable and no HubSpot company match to search under)'
            : ''),
    ];
    const summaryText = summaryLines.join('\n');
    ctx.log(summaryText);

    const result = {
      firmable_event_id: signal.id,
      company_id: signal.company_id,
      company_name: signal.company_name ?? (companyEnrichment?.name as string | undefined) ?? null,
      person_id: signal.person_id,
      person_name: signal.person_name,
      signal_type: signal.signal_type_slug,
      company_enrichment_status: companyEnrichmentStatus,
      person_enrichment_status: personEnrichmentStatus,
      company_domain: companyDomain,
      hubspot_match_by_domain: hubspotMatchByDomain,
      hubspot_match_by_firmable_id: hubspotMatchByFirmableId,
      hubspot_company_id: hubspotRecordId,
      hubspot_company_owner: companyOwner,
      hubspot_company_sdr: companySdr,
      person_exists_in_hubspot: personExistsInHubspot,
      hubspot_contact_owner: contactOwner,
      summary_text: summaryText,
    };

    // query_customer_db has no parameterized-query option (sql is a single string),
    // so every value is escaped via sqlString()/escapeSqlLiteral() before interpolation.
    await ctx.tools.execute({
      id: 'persist_new_joiner_check',
      tool: 'query_customer_db',
      input: {
        sql: `INSERT INTO analytics.firmable_new_joiner_checks
          (firmable_event_id, company_id, company_name, person_id, person_name, signal_type,
           company_enrichment_status, person_enrichment_status, company_domain,
           hubspot_match_by_domain, hubspot_match_by_firmable_id, hubspot_company_id,
           hubspot_company_owner, hubspot_company_sdr, person_exists_in_hubspot,
           hubspot_contact_owner, summary_text)
          VALUES (
            ${sqlString(result.firmable_event_id)},
            ${sqlString(result.company_id)},
            ${sqlString(result.company_name)},
            ${sqlString(result.person_id)},
            ${sqlString(result.person_name)},
            ${sqlString(result.signal_type)},
            ${sqlString(result.company_enrichment_status)},
            ${sqlString(result.person_enrichment_status)},
            ${sqlString(result.company_domain)},
            ${sqlBool(result.hubspot_match_by_domain)},
            ${sqlBool(result.hubspot_match_by_firmable_id)},
            ${sqlString(result.hubspot_company_id)},
            ${sqlString(result.hubspot_company_owner)},
            ${sqlString(result.hubspot_company_sdr)},
            ${sqlBool(result.person_exists_in_hubspot)},
            ${sqlString(result.hubspot_contact_owner)},
            ${sqlString(result.summary_text)}
          )`,
      },
      description: 'Persist the new-joiner enrichment + HubSpot match check + summary.',
    });

    return {
      ...result,
      company_enrichment: companyEnrichment,
      person_enrichment: personEnrichment,
    };
  },
  {
    // No HMAC yet — kept open (unguessable URL token only) to match the
    // echo-test play while we're still iterating with manual curl payloads.
    // Add the same webhook.hmac binding as firmable-bdr-signal-icp-check
    // before pointing real Firmable signal-agent traffic at this.
    description: 'Enrich new-joiner signal, check HubSpot match',
    webhook: {},
  },
);
