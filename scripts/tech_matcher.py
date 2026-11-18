"""
Match free-text product names (from the LLM) to rows in the Firmable technology counts CSV.

Flow per product name:
  1. Exact match on normalised name
  2. Otherwise build a shortlist: CSV names that start with / contain the query as whole words,
     plus difflib close matches
  3. Caller confirms the right shortlist entry with a small LLM call (see match_products in the tech-intel-outbound pipelines)
"""

import csv
import difflib
import re
from pathlib import Path

STRIP_WORDS = {"inc", "llc", "ltd", "corp", "co", "the", "platform", "software", "app", "io", "com", "ai"}


def normalise(name: str) -> str:
    name = name.lower().replace("&", " and ")
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    words = [w for w in name.split() if w not in STRIP_WORDS]
    return " ".join(words)


def _to_int(value) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


class TechCounts:
    def __init__(self, csv_path: Path, count_col: str = "NA_MATCHING", extra_cols: tuple = ()):
        """count_col drives count() and collision ranking; extra_cols (e.g. "APAC_MATCHING")
        are loaded alongside and read with count_in()."""
        self.count_col = count_col
        self.rows = {}           # exact TECHNOLOGY_NAME -> {"category", "count", "counts": {col: n}}
        self.by_norm = {}        # normalised name -> TECHNOLOGY_NAME (highest count wins on collision)
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                name = r["TECHNOLOGY_NAME"].strip()
                count = _to_int(r[count_col])
                self.rows[name] = {"category": r.get("CATEGORY_NAME", ""), "count": count,
                                   "counts": {c: _to_int(r.get(c)) for c in (count_col, *extra_cols)}}
                n = normalise(name)
                if n and (n not in self.by_norm or count > self.rows[self.by_norm[n]]["count"]):
                    self.by_norm[n] = name
        self._norm_keys = list(self.by_norm.keys())

    def count(self, name: str) -> int:
        return self.rows.get(name, {}).get("count", 0)

    def count_in(self, name: str, col: str) -> int:
        return self.rows.get(name, {}).get("counts", {}).get(col, 0)

    def exact(self, query: str):
        return self.by_norm.get(normalise(query))

    def shortlist(self, query: str, limit: int = 8) -> list:
        """Candidate TECHNOLOGY_NAMEs for a query, best-first. Empty if nothing plausible."""
        q = normalise(query)
        if not q:
            return []
        candidates = []
        pattern = re.compile(rf"(^| ){re.escape(q)}( |$)")
        word_hits = [self.by_norm[k] for k in self._norm_keys if pattern.search(k)]
        # Prefer names that start with the query, then by count (bigger = more likely the core product)
        word_hits.sort(key=lambda n: (not normalise(n).startswith(q), -self.count(n)))
        candidates.extend(word_hits[:limit])
        for k in difflib.get_close_matches(q, self._norm_keys, n=limit, cutoff=0.8):
            name = self.by_norm[k]
            if name not in candidates:
                candidates.append(name)
        return candidates[:limit]
