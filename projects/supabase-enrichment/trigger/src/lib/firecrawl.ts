// Firecrawl scrape helper — same pattern as enrich_accounts.py:233

export async function scrapeWebsite(domain: string): Promise<string | null> {
  const url = `https://${domain}`;
  try {
    const response = await fetch("https://api.firecrawl.dev/v1/scrape", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.FIRECRAWL_API_KEY}`,
      },
      body: JSON.stringify({
        url,
        formats: ["markdown"],
        onlyMainContent: true,
      }),
    });

    if (!response.ok) return null;

    const data = (await response.json()) as { success: boolean; data?: { markdown?: string } };
    if (!data.success || !data.data?.markdown) return null;

    // Truncate to 4,000 chars — same limit as enrich_accounts.py
    return data.data.markdown.slice(0, 4000) || null;
  } catch {
    return null;
  }
}
