"""
lit-review.py — Multi-pass academic literature review via Semantic Scholar
===========================================================================

A general-purpose tool for running comprehensive, structured lit reviews.
Runs multiple search passes from a YAML config, deduplicates across passes,
and outputs a tiered markdown file organized by relevance.

Three modes:
  1. RUN:         Execute a config of search passes
  2. GENERATE:    Create a config from your paper's metadata (title, abstract, keywords)
  3. INTERACTIVE: Guided wizard that walks you through building + running a review

USAGE:
    python lit-review.py config.yaml              → run all passes in config
    python lit-review.py config.yaml -pass 1-5    → run only passes 1-5
    python lit-review.py --generate input.yaml    → generate config from paper metadata
    python lit-review.py --example                → print example run config
    python lit-review.py --interactive            → guided wizard mode

Output: ~/Downloads/litrev_[name]_[date].md

TIERED OUTPUT:
    Tier 0 — KNOW THESE: published in your target venue or by editorial board members
    Tier 1 — MUST-READ:  3+ pass overlap, or 2+ overlap with high citations
    Tier 2 — STRONG:     2 pass overlap, or 1 pass with high citations
    Tier 3 — SCAN:       everything else (condensed: title + metadata only, no abstract)
"""

import sys
import io
import json
import time
import requests
import yaml
from pathlib import Path
from datetime import datetime
from itertools import combinations

# Fix Windows console encoding for Korean/special characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# --- Semantic Scholar API ---
CONFIG_PATH = Path(__file__).parent / ".litreview-config"
BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def load_api_key():
    """Load API key from config file."""
    if CONFIG_PATH.exists():
        return CONFIG_PATH.read_text(encoding="utf-8").strip()
    return ""


def save_api_key(key):
    """Save API key to config file."""
    CONFIG_PATH.write_text(key.strip(), encoding="utf-8")


API_KEY = load_api_key()
FIELDS = "title,abstract,authors,year,citationCount,url,publicationTypes,journal,fieldsOfStudy,externalIds"



# ============================================================================
# GENERATE MODE — create a config from paper metadata
# ============================================================================

def extract_noun_phrases(text):
    """Extract proper nouns and named concepts from abstract text."""
    import re
    phrases = set()

    # Quoted terms
    for m in re.finditer(r'"([^"]+)"', text):
        phrases.add(m.group(1).lower())
    for m in re.finditer(r"'([^']+)'", text):
        if len(m.group(1).split()) <= 4:
            phrases.add(m.group(1).lower())

    # Mid-sentence capitalized sequences (proper nouns)
    for m in re.finditer(r'(?<=\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text):
        candidate = m.group(1).lower()
        if len(candidate.split()) <= 4:
            phrases.add(candidate)

    # Single capitalized words mid-sentence (names, frameworks)
    for m in re.finditer(r'(?<=[a-z]\s)([A-Z][a-z]{2,})', text):
        phrases.add(m.group(1).lower())

    return phrases


def generate_config(input_config):
    """
    Generate a ~15-pass lit review config from paper metadata.
    Capped for quality over quantity — targets 200-300 results.
    """
    title = input_config.get("title", "")
    keywords = input_config.get("keywords", [])
    abstract = input_config.get("abstract", "")
    venues = input_config.get("venues", [])
    editorial_board = input_config.get("editorial_board", [])
    manual = input_config.get("manual", [])

    passes = []
    seen_queries = set()

    def add_pass(label, query, n=30, year=None, venue_list=None):
        # Dedup key includes venue + year so venue/recency passes don't collide
        dedup_key = f"{query.strip().lower()}|{year or ''}|{','.join(venue_list) if venue_list else ''}"
        if dedup_key in seen_queries:
            return
        seen_queries.add(dedup_key)
        p = {"label": label, "query": query, "n": n}
        if year:
            p["year"] = year
        if venue_list:
            p["venues"] = venue_list
        passes.append(p)

    # --- 1. Title search (1 pass) ---
    if title:
        add_pass(f"Title: {title[:50]}", title, n=20)

    # --- 2. Strongest keyword pairs (up to 5 passes) ---
    # First 5 combinations — user should order keywords by importance
    if len(keywords) >= 2:
        for a, b in list(combinations(keywords, 2))[:5]:
            add_pass(f"{a} + {b}", f"{a} {b}", n=30)

    # --- 3. Abstract proper nouns (1-2 passes) ---
    if abstract:
        abstract_phrases = extract_noun_phrases(abstract)
        kw_lower = {k.lower() for k in keywords}
        stopwords = {"the", "this", "that", "from", "with", "through", "paper",
                     "analysis", "framework", "approach", "study", "case", "form",
                     "drawing", "arguing", "asking", "examining", "tracing",
                     "becomes", "between", "reveals", "extends", "argues"}
        novel = {p for p in abstract_phrases - kw_lower
                 if len(p) > 4
                 and p not in stopwords
                 and "'" not in p and not p.startswith("s ")}
        for phrase in sorted(novel)[:3]:
            add_pass(f"Abstract: {phrase}", phrase, n=15)

    # --- 5. Editorial board author searches (1 pass per member, short) ---
    if editorial_board:
        broad_kw = keywords[0] if keywords else ""
        for name in editorial_board:
            add_pass(f"Board: {name}", f"{name} {broad_kw}", n=10)

    # --- 6. Venue targeting (1 pass per venue) ---
    for venue in venues:
        broad_query = " ".join(keywords[:3]) if len(keywords) >= 3 else " ".join(keywords)
        add_pass(f"Venue: {venue}", broad_query, n=30, year="2022-", venue_list=[venue])

    # --- 7. Manual searches ---
    for m in manual:
        add_pass(m.get("label", "Manual"), m.get("query", ""), n=m.get("n", 20))

    # --- 8. Recency sweep (1 pass) ---
    broad_query = " ".join(keywords[:3]) if len(keywords) >= 3 else " ".join(keywords)
    add_pass("Recency (2024+)", broad_query, n=40, year="2024-")

    # --- Output ---
    seed_dois = input_config.get("seed_dois", [])
    config = {
        "name": title or "Generated Review",
        "defaults": {"n": 30},
        "venues": venues,
        "editorial_board": editorial_board,
        "passes": passes,
    }
    if seed_dois:
        config["seed_dois"] = seed_dois

    print("# Auto-generated lit review config")
    print(f"# From: {title}")
    print(f"# Keywords: {', '.join(keywords)}")
    if editorial_board:
        print(f"# Editorial board: {', '.join(editorial_board)}")
    print(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"# {len(passes)} passes")
    print()
    print(yaml.dump(config, default_flow_style=False, allow_unicode=True, sort_keys=False))


# ============================================================================
# RUN MODE — execute passes and produce tiered output
# ============================================================================

EXAMPLE_CONFIG = """
# Lit Review Config
name: "My Paper Title"

defaults:
  n: 30

# Target venues — papers published here get Tier 0
venues:
  - "Target Journal"

# Editorial board — papers by these people get Tier 0
editorial_board:
  - "Board Member Name"

passes:
  - label: "Core concept search"
    query: "your main concept here"
    n: 50

  - label: "Theory + application"
    query: "theory name applied to domain"

  - label: "Recency sweep"
    query: "broad topic keywords"
    year: "2024-"
    n: 50
""".strip()


def fetch_paper_by_doi(doi):
    """Look up a single paper by DOI via Semantic Scholar."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    params = {"fields": FIELDS}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"      Request error: {e}")
        return None
    if resp.status_code == 429:
        print(f"      Rate limited — waiting 5s...")
        time.sleep(5)
        return fetch_paper_by_doi(doi)
    if resp.status_code != 200:
        print(f"      Error {resp.status_code} for DOI {doi}")
        return None
    return resp.json()


def fetch_references(paper_id):
    """Fetch the bibliography (references) of a paper via Semantic Scholar."""
    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references"
    headers = {"x-api-key": API_KEY} if API_KEY else {}
    params = {"fields": FIELDS, "limit": 500}
    all_refs = []
    offset = 0

    while True:
        params["offset"] = offset
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"      Request error: {e}")
            break

        if resp.status_code == 429:
            print(f"      Rate limited — waiting 5s...")
            time.sleep(5)
            continue

        if resp.status_code != 200:
            print(f"      Error {resp.status_code}")
            break

        data = resp.json()
        refs = data.get("data", [])
        if not refs:
            break

        for ref in refs:
            cited = ref.get("citedPaper")
            if cited and cited.get("paperId"):
                all_refs.append(cited)

        offset += len(refs)
        if offset >= data.get("total", 0):
            break
        time.sleep(0.15)

    return all_refs


def search_pass(query, limit=30, year_range=None):
    """Run one search against Semantic Scholar API."""
    all_results = []
    offset = 0
    batch_size = min(limit, 100)

    while len(all_results) < limit:
        params = {
            "query": query,
            "limit": batch_size,
            "offset": offset,
            "fields": FIELDS,
        }
        if year_range:
            params["year"] = year_range

        headers = {"x-api-key": API_KEY} if API_KEY else {}

        try:
            resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"    Request error: {e}")
            break

        if resp.status_code == 429:
            print(f"    Rate limited — waiting 5s...")
            time.sleep(5)
            continue

        if resp.status_code != 200:
            print(f"    Error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        papers = data.get("data", [])
        total = data.get("total", 0)

        if not papers:
            break

        all_results.extend(papers)
        offset += len(papers)

        if offset >= total or offset >= limit:
            break

        time.sleep(0.15)

    return all_results[:limit]


def format_paper(paper, index, tier=3, overlap_count=1, overlap_passes=None, ref_count=0):
    """
    Format a paper based on tier:
      Tier 0-1: full format with abstract
      Tier 2:   condensed — title, authors, journal, citations, link (no abstract)
      Tier 3:   title only — title + year + citations for scanning
    """
    title = paper.get("title") or "Untitled"
    year = paper.get("year") or "n.d."
    citations = paper.get("citationCount") or 0
    url = paper.get("url") or ""

    authors = paper.get("authors") or []
    author_str = ", ".join(a.get("name", "?") for a in authors[:5])
    if len(authors) > 5:
        author_str += f" + {len(authors) - 5} more"

    journal = paper.get("journal") or {}
    journal_name = journal.get("name") or ""

    ext_ids = paper.get("externalIds") or {}
    doi = ext_ids.get("DOI") or ""

    fields = paper.get("fieldsOfStudy") or []
    fields_str = ", ".join(fields) if fields else ""

    overlap_tag = f" `[x{overlap_count}]`" if overlap_count > 1 else ""
    ref_tag = f" `[+ref{ref_count}]`" if ref_count > 0 else ""

    # Tier 3: title-only scan line
    if tier == 3:
        cite_str = f"{citations} cites" if citations else "0 cites"
        link = f" [→]({url})" if url else ""
        return f"- {title} ({year}) — {cite_str}{ref_tag}{link}\n"

    # Tier 2: condensed — metadata but no abstract
    if tier == 2:
        meta = f"({year}) **{author_str}**"
        if journal_name:
            meta += f" — *{journal_name}*"
        meta += f" | {citations} cites"
        if url:
            meta += f" | [SS]({url})"
        return f"### {index}. {title}{overlap_tag}{ref_tag}\n{meta}\n\n---\n\n"

    # Tier 0-1: full format with abstract
    tier_labels = {0: "VENUE/BOARD", 1: "MUST-READ"}
    tier_tag = f" `[{tier_labels.get(tier, '')}]`" if tier in tier_labels else ""

    lines = [f"### {index}. {title} ({year}){overlap_tag}{ref_tag}{tier_tag}"]
    if overlap_passes and overlap_count > 1:
        lines.append(f"*Appeared in: {', '.join(overlap_passes)}*")
    lines.append(f"**{author_str}**")
    if journal_name:
        lines.append(f"*{journal_name}*")
    meta_parts = [f"Citations: {citations}"]
    if fields_str:
        meta_parts.append(f"Fields: {fields_str}")
    lines.append(" | ".join(meta_parts))
    if doi:
        lines.append(f"DOI: {doi}")
    if url:
        lines.append(f"[Semantic Scholar]({url})")
    lines.append("")
    abstract = paper.get("abstract") or "*No abstract available.*"
    lines.append(abstract)
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def assign_tier(paper, overlap_count, venue_names, board_names):
    """
    Assign a tier (0-3) to a paper based on:
      - Tier 0: venue match OR editorial board author match
      - Tier 1: 3+ overlap, or 2+ overlap with 50+ citations
      - Tier 2: 2 overlap, or 1 overlap with 100+ citations
      - Tier 3: everything else
    """
    citations = paper.get("citationCount") or 0

    # Tier 0: venue or board match
    journal = paper.get("journal") or {}
    jname = (journal.get("name") or "").lower()
    for v in venue_names:
        if v.lower() in jname:
            return 0

    authors = paper.get("authors") or []
    author_names_lower = {a.get("name", "").lower() for a in authors}
    for board_name in board_names:
        if board_name.lower() in author_names_lower:
            return 0

    # Tier 1
    if overlap_count >= 3:
        return 1
    if overlap_count >= 2 and citations >= 50:
        return 1

    # Tier 2
    if overlap_count >= 2:
        return 2

    # Tier 3
    return 3



def parse_pass_range(arg, total):
    """Parse a pass range string like '1-5' or '3' into 0-indexed set."""
    if "-" in arg:
        parts = arg.split("-", 1)
        start = int(parts[0]) - 1 if parts[0] else 0
        end = int(parts[1]) if parts[1] else total
        return set(range(start, end))
    else:
        return {int(arg) - 1}


def run_review(config, pass_filter=None):
    """Run all (or selected) passes from a config dict, produce tiered output."""
    name = config.get("name", "Untitled Review")
    defaults = config.get("defaults", {})
    passes = config.get("passes", [])
    venue_names = config.get("venues", [])
    board_names = config.get("editorial_board", [])

    if not passes:
        print("No passes defined in config.")
        return

    # Apply pass filter
    if pass_filter is not None:
        indices = parse_pass_range(pass_filter, len(passes))
        active_passes = [(i, p) for i, p in enumerate(passes) if i in indices]
    else:
        active_passes = list(enumerate(passes))

    print(f"=== Lit Review: {name} ===")
    print(f"  Running {len(active_passes)} of {len(passes)} passes")
    if venue_names:
        print(f"  Target venues: {', '.join(venue_names)}")
    if board_names:
        print(f"  Editorial board: {len(board_names)} members")
    print()

    # Track overlap
    paper_registry = {}   # pid → paper dict
    paper_passes = {}     # pid → list of pass labels
    all_sections = []     # (label, [papers])
    total_found = 0
    total_unique = 0

    for seq, (i, pass_cfg) in enumerate(active_passes, 1):
        label = pass_cfg.get("label", f"Pass {i+1}")
        query = pass_cfg.get("query", "")
        if not query:
            print(f"  [{seq}/{len(active_passes)}] {label} — SKIPPED (no query)")
            continue

        n = pass_cfg.get("n", defaults.get("n", 30))
        year = pass_cfg.get("year", defaults.get("year"))
        min_cites = pass_cfg.get("min_citations", defaults.get("min_citations", 0))
        venue_filter = pass_cfg.get("venues")

        print(f"  [{seq}/{len(active_passes)}] {label}")
        print(f"    query: \"{query}\"", end="")
        if year:
            print(f" | year: {year}", end="")
        print(f" | max: {n}")

        results = search_pass(query, limit=n, year_range=year)
        print(f"    raw: {len(results)}", end="")

        new_in_pass = []
        dupes_in_pass = 0
        for paper in results:
            pid = paper.get("paperId")
            if not pid:
                continue
            if min_cites and (paper.get("citationCount") or 0) < min_cites:
                continue
            if venue_filter:
                j = paper.get("journal") or {}
                jname = (j.get("name") or "").lower()
                if not any(v.lower() in jname for v in venue_filter):
                    continue

            if pid in paper_registry:
                paper_passes[pid].append(label)
                dupes_in_pass += 1
            else:
                paper_registry[pid] = paper
                paper_passes[pid] = [label]
                new_in_pass.append(paper)

        new_in_pass.sort(key=lambda p: p.get("citationCount") or 0, reverse=True)

        total_found += len(results)
        total_unique += len(new_in_pass)
        print(f" → {len(new_in_pass)} new, {dupes_in_pass} overlap")

        if new_in_pass:
            all_sections.append((label, new_in_pass))

        time.sleep(0.3)

    # --- Seed papers: fetch by DOI and force into citation chase ---
    seed_dois = config.get("seed_dois", [])
    seed_pids = set()
    if seed_dois:
        print(f"\n  --- Fetching {len(seed_dois)} seed papers by DOI ---")
        for doi in seed_dois:
            print(f"    DOI: {doi}...", end="", flush=True)
            paper = fetch_paper_by_doi(doi)
            if paper and paper.get("paperId"):
                pid = paper["paperId"]
                ptitle = (paper.get("title") or "Untitled")[:60]
                if pid not in paper_registry:
                    paper_registry[pid] = paper
                    paper_passes[pid] = ["seed"]
                    total_unique += 1
                    print(f" {ptitle} (new)")
                else:
                    paper_passes[pid].append("seed")
                    print(f" {ptitle} (already found)")
                seed_pids.add(pid)
            else:
                print(f" not found on Semantic Scholar")
            time.sleep(0.3)

    # --- Citation chase: fetch bibliographies of 3+ overlap papers + seed papers ---
    # Only chase papers that appeared in 3+ search passes (core field papers),
    # PLUS any seed papers regardless of overlap.
    # Ref overlap is tracked SEPARATELY — it doesn't inflate tier assignment.
    paper_ref_count = {}  # pid → number of chased bibliographies it appeared in

    chase_candidates = []
    for pid, paper in paper_registry.items():
        oc = len(paper_passes.get(pid, []))
        if oc >= 3 or pid in seed_pids:
            chase_candidates.append((pid, paper, oc))

    if chase_candidates:
        chase_candidates.sort(key=lambda x: (x[2], x[1].get("citationCount") or 0), reverse=True)
        print(f"\n  --- Citation chase: fetching bibliographies of {len(chase_candidates)} papers (3+ overlap) ---")
        for pid, paper, oc in chase_candidates:
            ptitle = (paper.get("title") or "Untitled")[:60]
            print(f"    Refs: {ptitle}...", end="", flush=True)
            refs = fetch_references(pid)
            new_refs = 0
            existing_refs = 0
            for ref in refs:
                rpid = ref.get("paperId")
                if not rpid:
                    continue
                # Track ref overlap separately
                paper_ref_count[rpid] = paper_ref_count.get(rpid, 0) + 1
                # Add new papers to registry but do NOT add to paper_passes
                if rpid not in paper_registry:
                    paper_registry[rpid] = ref
                    paper_passes[rpid] = []  # no search-pass overlap
                    new_refs += 1
                else:
                    existing_refs += 1
            total_unique += new_refs
            print(f" {len(refs)} refs → {new_refs} new, {existing_refs} already known")
            time.sleep(0.3)
        print()

    # --- Assign tiers (ref overlap does NOT affect tier assignment) ---
    # Seed papers are excluded from tiered output — you already know to read them.
    tiered = {0: [], 1: [], 2: [], 3: []}
    for pid, paper in paper_registry.items():
        if pid in seed_pids:
            continue
        overlap_count = len(paper_passes.get(pid, []))
        passes_list = paper_passes.get(pid, [])
        ref_count = paper_ref_count.get(pid, 0)
        tier = assign_tier(paper, overlap_count, venue_names, board_names)
        tiered[tier].append((pid, paper, overlap_count, passes_list, ref_count))

    # Sort each tier: overlap desc → ref count desc → citations desc → year desc
    for t in tiered:
        tiered[t].sort(key=lambda x: (
            x[2],                                    # search-pass overlap
            x[4],                                    # ref overlap (tiebreaker)
            x[1].get("citationCount") or 0,          # citations
            x[1].get("year") or 0,                   # recency
        ), reverse=True)

    # --- Build output ---
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_name = name.replace(" ", "_").replace("/", "-")[:40]
    date_str = datetime.now().strftime("%Y%m%d")
    outputs_dir = Path(__file__).parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    output_path = outputs_dir / f"litrev_{safe_name}_{date_str}.md"

    lines = [
        f"# Lit Review: {name}",
        "",
        f"*Generated {now} | {len(active_passes)} passes | {total_found} raw | {total_unique} unique after dedup*",
        "",
    ]

    # Summary
    lines.append("## Summary\n")
    lines.append(f"| Tier | Count | Description |")
    lines.append(f"|------|-------|-------------|")
    lines.append(f"| **Tier 0** | {len(tiered[0])} | Venue match or editorial board |")
    lines.append(f"| **Tier 1** | {len(tiered[1])} | Must-read (high overlap + citations) |")
    lines.append(f"| **Tier 2** | {len(tiered[2])} | Strong candidates |")
    lines.append(f"| **Tier 3** | {len(tiered[3])} | Scan (condensed) |")
    lines.append(f"| **Total** | {total_unique} | |")
    lines.append("")
    if venue_names:
        lines.append(f"**Target venues:** {', '.join(venue_names)}")
    if board_names:
        lines.append(f"**Editorial board:** {', '.join(board_names)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    global_index = 1

    # Seed papers
    if seed_pids:
        lines.append("## seed papers (your bibliography)\n")
        lines.append("*the papers you provided. we did some bibliography chasing on this to add to the overlap scores!*\n")
        for pid in seed_pids:
            paper = paper_registry.get(pid)
            if paper:
                title = paper.get("title") or "Untitled"
                year = paper.get("year") or "n.d."
                citations = paper.get("citationCount") or 0
                url = paper.get("url") or ""
                authors = paper.get("authors") or []
                author_str = ", ".join(a.get("name", "?") for a in authors[:5])
                ext_ids = paper.get("externalIds") or {}
                doi = ext_ids.get("DOI") or ""
                ref_count = paper_ref_count.get(pid, 0)
                link = f" | [SS]({url})" if url else ""
                doi_str = f" | DOI: {doi}" if doi else ""
                lines.append(f"- **{title}** ({year}) — {author_str} | {citations} cites{doi_str}{link}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Tier 0
    if tiered[0]:
        lines.append("## Tier 0 — KNOW THESE\n")
        lines.append("*you better be aware of these -- they were published in your target venues or by their editorial staff!*\n")
        for pid, paper, oc, pl, rc in tiered[0]:
            lines.append(format_paper(paper, global_index, tier=0,
                                      overlap_count=oc, overlap_passes=pl, ref_count=rc))
            global_index += 1

    # Tier 1
    if tiered[1]:
        lines.append("## Tier 1 — MUST-READ\n")
        lines.append("*high overlap across search angles and/or highly cited.*\n")
        for pid, paper, oc, pl, rc in tiered[1]:
            lines.append(format_paper(paper, global_index, tier=1,
                                      overlap_count=oc, overlap_passes=pl, ref_count=rc))
            global_index += 1

    # Tier 2
    if tiered[2]:
        lines.append("## Tier 2 — STRONG CANDIDATES\n")
        lines.append("*appeared in multiple searches or well-cited in the field.*\n")
        for pid, paper, oc, pl, rc in tiered[2]:
            lines.append(format_paper(paper, global_index, tier=2,
                                      overlap_count=oc, overlap_passes=pl, ref_count=rc))
            global_index += 1

    # Tier 3
    if tiered[3]:
        lines.append("## Tier 3 — SCAN\n")
        lines.append(f"*{len(tiered[3])} papers. we've collected only the titles for these, but some of these might catch your eye.*\n")
        for pid, paper, oc, pl, rc in tiered[3]:
            lines.append(format_paper(paper, global_index, tier=3, ref_count=rc))
            global_index += 1

    lines.append("")
    lines.append("---")
    lines.append("")

    # Pass-by-pass breakdown (appendix)
    lines.append("## Appendix: Pass Breakdown\n")
    for label, papers in all_sections:
        lines.append(f"- **{label}** ({len(papers)} papers)")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n=== Done ===")
    print(f"  Total raw: {total_found}")
    print(f"  Unique papers: {total_unique}")
    print(f"  Tier 0 (venue/board): {len(tiered[0])}")
    print(f"  Tier 1 (must-read):   {len(tiered[1])}")
    print(f"  Tier 2 (strong):      {len(tiered[2])}")
    print(f"  Tier 3 (scan):        {len(tiered[3])}")
    print(f"  Saved to: {output_path}")
    return output_path


# ============================================================================
# INTERACTIVE MODE — guided wizard
# ============================================================================

# ---- INSTRUCTIONS ----
# Edit these strings to change what the user sees at each step.
# Each key corresponds to a step in the wizard.
STEP_INSTRUCTIONS = {
    "welcome": """
=== smart lit review (semantic scholar) v0.1 ===
this tool pulls abstracts and titles from semantic scholar to assist in your lit review! 
""",

    "title": """
--- Step 1: Title ---
the title of your paper
""",

    "keywords": """
--- Step 2: Keywords ---
keywords (by order of importance): the keywords will be used to generate search pairs.
""",

    "abstract": """
--- Step 3: Abstract ---
your abstract, or any summary of what you intend to write. 
""",

    "venues": """
--- Step 4: Target Venues ---
your target venues?
""",

    "editorial_board": """
--- Step 5: Editorial Board ---
paste the editorial board list of your target venues here.
""",

    "manual_searches": """
--- Step 6: Manual Searches ---
specific authors, case studies, field vocabulary, anything you want to add that a dumb semantic parser wouldn't recognize from your abstract? 
""",

    "seed_papers": """
--- Step 7: Seed Papers (DOIs) ---
enter the dois of the papers you already intend to use! one by one (press enter after you put one in.)
""",

    "review_passes": """
--- Generated Passes ---
here are the search terms we came up with! do any of them need editing?
""",

    "done": """
config saved. Run it with:
  python lit-review.py {path}
or type 'run' to execute now.
""",
}
# ---- END INSTRUCTIONS ----


def prompt_input(prompt_text, allow_blank=True):
    """Get a single line of input."""
    val = input(prompt_text).strip()
    if not val and not allow_blank:
        print("  (This field is required.)")
        return prompt_input(prompt_text, allow_blank=False)
    return val


def prompt_list(prompt_text, separator=","):
    """Get a comma-separated list, return as list of strings."""
    val = input(prompt_text).strip()
    if not val:
        return []
    return [x.strip() for x in val.split(separator) if x.strip()]


def prompt_multiline(prompt_text):
    """Get multiline input. Blank line to finish."""
    print(prompt_text)
    lines = []
    while True:
        line = input("  > ")
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def display_passes(passes):
    """Pretty-print the generated passes as a numbered list."""
    print()
    for i, p in enumerate(passes):
        n = p.get("n", 30)
        extra = ""
        if p.get("year"):
            extra += f"  year: {p['year']}"
        if p.get("venues"):
            extra += f"  venues: {','.join(p['venues'])}"
        suffix = f"  (n={n}{extra})" if extra else f"  (n={n})"
        print(f"  {i+1:>2}. \"{p['query']}\"{suffix}")
    print(f"\n  {len(passes)} passes total.")


def edit_passes_loop(passes):
    """Let the user add/remove/edit passes interactively."""
    while True:
        print()
        print("  What would you like to do?")
        print("    [number]  edit a pass        [a] add a pass")
        print("    [d]       delete a pass       [done] save and finish")
        print("                                  [q] quit without saving")
        action = prompt_input("\n  > ")

        a = action.strip().lower()

        if a in ("done", "save", "run"):
            return "save"
        if a in ("quit", "q"):
            return "quit"

        if a == "a":
            query = prompt_input("    Search query: ", allow_blank=False)
            n = prompt_input("    Max results [20]: ") or "20"
            passes.append({"label": query[:50], "query": query, "n": int(n)})
            print(f"    Added #{len(passes)}: \"{query}\"")
            display_passes(passes)

        elif a == "d":
            num = prompt_input("    Which pass number to delete? ")
            try:
                idx = int(num) - 1
                if 0 <= idx < len(passes):
                    removed = passes.pop(idx)
                    print(f"    Deleted: \"{removed['query']}\"")
                    display_passes(passes)
                else:
                    print(f"    No pass #{num}. Range: 1-{len(passes)}")
            except ValueError:
                print("    Enter a number.")

        elif a.isdigit():
            idx = int(a) - 1
            if 0 <= idx < len(passes):
                p = passes[idx]
                print(f"\n    Editing #{int(a)}: \"{p['query']}\"")
                new_query = prompt_input(f"    New query (Enter to keep): ") or p['query']
                new_n = prompt_input(f"    Max results [{p.get('n', 30)}]: ") or str(p.get('n', 30))
                p['query'] = new_query
                p['n'] = int(new_n)
                p['label'] = new_query[:50]
                print(f"    Updated #{int(a)}.")
            else:
                print(f"    No pass #{a}. Range: 1-{len(passes)}")

        else:
            print("    Enter a pass number to edit, or: a / d / run / save / q")


def interactive_mode():
    """Guided wizard for building and running a lit review."""
    import re

    print(STEP_INSTRUCTIONS["welcome"])

    # API key check
    global API_KEY
    if API_KEY:
        masked = API_KEY[:6] + "..." + API_KEY[-4:]
        print(f"  API key: {masked}")
    else:
        print("  No Semantic Scholar API key found.")
        print("  Get one free at: https://www.semanticscholar.org/product/api#api-key")
        new_key = prompt_input("  API key: ", allow_blank=False)
        save_api_key(new_key)
        API_KEY = new_key
        print("  Key saved.")
    print()

    # Step 1: Title
    print(STEP_INSTRUCTIONS["title"])
    title = prompt_input("  Paper title: ", allow_blank=False)

    # Step 2: Keywords
    print(STEP_INSTRUCTIONS["keywords"])
    keywords = prompt_list("  Keywords (comma-separated): ")
    while len(keywords) < 2:
        print("  (Need at least 2 keywords to generate pairs.)")
        keywords = prompt_list("  Keywords (comma-separated): ")

    # Step 3: Abstract
    print(STEP_INSTRUCTIONS["abstract"])
    abstract = prompt_multiline("  Paste abstract (blank line to finish, or just press Enter to skip):")

    # Step 4: Venues
    print(STEP_INSTRUCTIONS["venues"])
    venues = prompt_list("  Target venues (comma-separated, or blank): ")

    # Step 5: Editorial board
    print(STEP_INSTRUCTIONS["editorial_board"])
    board = prompt_list("  Board member names (comma-separated, or blank): ")

    # Step 6: Manual searches
    print(STEP_INSTRUCTIONS["manual_searches"])
    manual = []
    while True:
        query = prompt_input("  Search query (or blank to finish): ")
        if not query:
            break
        manual.append({"label": query[:50], "query": query, "n": 20})
        print(f"    Added: {query}")

    # Step 7: Seed papers
    print(STEP_INSTRUCTIONS["seed_papers"])
    seed_dois = []
    while True:
        doi = prompt_input("  DOI (or blank to finish): ")
        if not doi:
            break
        # Strip common prefixes
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        seed_dois.append(doi)
        print(f"    Added: {doi}")

    # Build the input config
    input_config = {
        "title": title,
        "keywords": keywords,
        "abstract": abstract,
        "venues": venues,
        "editorial_board": board,
        "manual": manual,
        "seed_dois": seed_dois,
    }

    # Generate passes (reuse existing logic but capture instead of printing)
    # We'll build passes directly here to include additional terms
    passes = []
    seen_queries = set()

    def add_pass(label, query, n=30, year=None, venue_list=None):
        dedup_key = f"{query.strip().lower()}|{year or ''}|{','.join(venue_list) if venue_list else ''}"
        if dedup_key in seen_queries:
            return
        seen_queries.add(dedup_key)
        p = {"label": label, "query": query, "n": n}
        if year:
            p["year"] = year
        if venue_list:
            p["venues"] = venue_list
        passes.append(p)

    # 1. Title
    if title:
        add_pass(f"Title: {title[:50]}", title, n=20)

    # 2. Keyword pairs (top 5)
    if len(keywords) >= 2:
        for a, b in list(combinations(keywords, 2))[:5]:
            add_pass(f"{a} + {b}", f"{a} {b}", n=30)

    # 3. Abstract proper nouns
    if abstract:
        abstract_phrases = extract_noun_phrases(abstract)
        kw_lower = {k.lower() for k in keywords}
        stopwords = {"the", "this", "that", "from", "with", "through", "paper",
                     "analysis", "framework", "approach", "study", "case", "form",
                     "drawing", "arguing", "asking", "examining", "tracing",
                     "becomes", "between", "reveals", "extends", "argues"}
        novel = {p for p in abstract_phrases - kw_lower
                 if len(p) > 4
                 and p not in stopwords
                 and "'" not in p and not p.startswith("s ")}
        for phrase in sorted(novel)[:3]:
            add_pass(f"Abstract: {phrase}", phrase, n=15)

    # 5. Board member searches
    if board:
        broad_kw = keywords[0] if keywords else ""
        for name in board:
            add_pass(f"Board: {name}", f"{name} {broad_kw}", n=10)

    # 7. Venue targeting
    for venue in venues:
        broad_query = " ".join(keywords[:3]) if len(keywords) >= 3 else " ".join(keywords)
        add_pass(f"Venue: {venue}", broad_query, n=30, year="2022-", venue_list=[venue])

    # 8. Manual searches
    for m in manual:
        add_pass(m.get("label", "Manual"), m.get("query", ""), n=m.get("n", 20))

    # 9. Recency sweep
    broad_query = " ".join(keywords[:3]) if len(keywords) >= 3 else " ".join(keywords)
    add_pass("Recency (2024+)", broad_query, n=40, year="2024-")

    # Show passes for review
    print(STEP_INSTRUCTIONS["review_passes"])
    display_passes(passes)

    # Edit loop
    result = edit_passes_loop(passes)

    # Build final config
    config = {
        "name": title,
        "defaults": {"n": 30},
        "venues": venues,
        "editorial_board": board,
        "passes": passes,
    }
    if seed_dois:
        config["seed_dois"] = seed_dois

    if result == "quit":
        print("  Exited without saving.")
        return

    # Save YAML
    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = re.sub(r'[^\w\-]', '_', title)[:30]
    queries_dir = Path(__file__).parent / "queries"
    queries_dir.mkdir(exist_ok=True)
    default_path = queries_dir / f"review_{safe_name}_{date_str}.yaml"
    save_path = prompt_input(f"  Save path [{default_path}]: ") or str(default_path)
    yaml_path = Path(save_path)

    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"# Generated interactively {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# {len(passes)} passes\n\n")
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\n  Saved to: {yaml_path}")

    run_now = prompt_input("\n  Run now? (y/n): ")
    if run_now.lower() in ("y", "yes", ""):
        print()
        run_review(config)
    else:
        print(f"\n  To run later:")
        print(f"    python lit-review.py \"{yaml_path}\"")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        interactive_mode()
        sys.exit(0)

    if sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  python lit-review.py                          Guided wizard (default)")
        print("  python lit-review.py config.yaml              Run all passes")
        print("  python lit-review.py config.yaml -pass 1-5    Run passes 1-5")
        print("  python lit-review.py config.yaml -pass 3      Run pass 3 only")
        print("  python lit-review.py --interactive              Guided wizard mode")
        print("  python lit-review.py --generate input.yaml    Generate config from paper metadata")
        print("  python lit-review.py --example                Print example config")
        sys.exit(0)

    if sys.argv[1] == "--interactive":
        interactive_mode()
        sys.exit(0)

    if sys.argv[1] == "--generate":
        if len(sys.argv) < 3:
            print("Usage: python lit-review.py --generate input.yaml > output.yaml")
            sys.exit(1)
        input_path = Path(sys.argv[2])
        if not input_path.exists():
            print(f"Input not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        with open(input_path, encoding="utf-8") as f:
            input_config = yaml.safe_load(f)
        generate_config(input_config)
        sys.exit(0)

    if sys.argv[1] == "--example":
        print(EXAMPLE_CONFIG)
        sys.exit(0)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Parse optional -pass flag
    pass_filter = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "-pass" and i + 1 < len(sys.argv):
            pass_filter = sys.argv[i + 1]

    run_review(config, pass_filter=pass_filter)
