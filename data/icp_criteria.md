# ICP Scoring Rubric

Used by lead scoring scripts to assign a numeric score and tier to each company or contact.
Total score determines routing: which outreach track, which SmartLead campaign, or whether to flag for manual review.

---

## Scoring Dimensions

### 1. Sales Team Size
*Sourced from Firmable API (`sales_team_size` field). Higher is always better.*

| Sales Team Size | Points |
|-----------------|--------|
| 20+             | 25     |
| 10–19           | 20     |
| 5–9             | 15     |
| 2–4             | 8      |
| 1               | 3      |
| 0 / unknown     | 0      |

---

### 2. Company Type / Industry
*Based on industry classification returned by Firmable or Clay enrichment.*

| Company Type                                  | Points | Notes                                                      |
|-----------------------------------------------|--------|------------------------------------------------------------|
| SaaS / Software                               | 25     | Highest fit — outbound-driven, budget exists, APAC-focused |
| Recruitment / Staffing                        | 20     | High BD activity, large contact databases, APAC-focused    |
| Consulting / Professional Services            | 15     | B2B sales motion, often ANZ-focused                        |
| Financial Services                            | 15     | B2B sales, compliance-conscious (DNC fit is a plus)        |
| Real Estate / PropTech                        | 12     | B2B sales teams, APAC footprint                            |
| Other B2B (logistics, construction, etc.)     | 8      | Moderate fit — evaluate on other signals                   |
| B2C / Consumer                                | 0      | Poor fit — no outbound B2B sales motion                    |
| Unknown / Unclear                             | 0      |                                                            |

---

### 3. Sales Function Signals
*Detected from job postings, LinkedIn headcount by department, or contact titles in the company.*

| Signal                                                                 | Points | Notes                                                     |
|------------------------------------------------------------------------|--------|-----------------------------------------------------------|
| SDR / BDR roles exist (job postings or headcount detected)             | 20     | Mature outbound motion — highest signal                   |
| Sales team with AE / Account Manager roles                             | 12     | Established sales function                                |
| Recruitment consultants (BD-style role in a recruitment firm)          | 20     | Direct analogue to SDR in this vertical                   |
| Founder-led sales (no sales titles, small team)                        | 5      | Potential fit but lower priority                          |
| No sales function signals                                              | 0      |                                                           |

---

### 4. Competitive Tech Stack
*Detected via Firmable technographics or Clay enrichment. These companies are problem-aware and open to switching.*

| Tech Detected                         | Points | Track                    |
|---------------------------------------|--------|--------------------------|
| ZoomInfo                              | 20     | Problem-aware (APAC gap) |
| Apollo.io                             | 20     | Problem-aware (APAC gap) |
| Lusha                                 | 20     | Problem-aware (APAC gap) |
| Cognism                               | 20     | Problem-aware (APAC gap) |
| LinkedIn Sales Navigator only         | 10     | Semi-aware               |
| No outbound data tool detected        | 0      | Not problem-aware        |

> **Note:** If competitive tech is detected, route to the competitor displacement email track regardless of total score.

---

## Score Tiers

| Total Score | Tier   | Routing                                                                 |
|-------------|--------|-------------------------------------------------------------------------|
| 70+         | Tier 1 | Priority. Flag for call-first outreach if competitive tech detected. Else top email sequence. |
| 40–69       | Tier 2 | Standard email sequence.                                                |
| 20–39       | Tier 3 | Lower priority. Nurture sequence or hold for future campaign.           |
| <20         | DQ     | Do not contact. Remove from active lists.                               |

---

## Maximum Possible Score

| Dimension             | Max Points |
|-----------------------|------------|
| Sales team size       | 25         |
| Company type          | 25         |
| Sales function signal | 20         |
| Competitive tech      | 20         |
| **Total**             | **90**     |

---

## Notes
- Scores are additive. Award points from each dimension independently.
- Sales team size data comes from the Firmable API — if unavailable, score 0 for that dimension and note as `sales_team_size_unknown`.
- Competitive tech detection is a routing override: regardless of tier, detected ZoomInfo/Apollo/Lusha/Cognism users go to the competitor displacement track.
- DNC exclusion is applied before scoring — see `data/exclusions.md`.
- Update this rubric as new signals are validated against conversion data.
