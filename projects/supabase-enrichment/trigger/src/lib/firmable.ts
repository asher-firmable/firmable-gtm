const BASE_URL = "https://api.firmable.com";

export async function fetchFirmableDescription(firmableId: string): Promise<string | null> {
  const apiKey = process.env.FIRMABLE_API_KEY;
  if (!apiKey) return null;

  try {
    const res = await fetch(`${BASE_URL}/company?id=${encodeURIComponent(firmableId)}`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!res.ok) return null;
    const data = await res.json() as { description?: string; tagline?: string };
    return data.description?.trim() || data.tagline?.trim() || null;
  } catch {
    return null;
  }
}
