---
name: crossref-search
description: Search Crossref's 188M+ DOI records (journal articles, books, book chapters, conference papers) through its free public REST API, no API key. Use this skill whenever the user wants to find scholarly articles or chapters by topic, author, or journal; look up or verify a DOI; turn a free-text reference into a DOI; format a citation (Chicago, APA, MLA, BibTeX, RIS); list a work's references or its citation count; browse a journal by ISSN; or find JSTOR links (3.3M JSTOR DOIs with prefix 10.2307). Also use it to check which agency registered a DOI (Crossref, DataCite, CNKI, ISTIC, Airiti).
version: 1.0.1
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# Crossref Search Skill

Search the metadata that publishers deposit with Crossref when they register DOIs. No API key needed.

## Overview

**Crossref** is the largest DOI registration agency. Its REST API (`https://api.crossref.org`) returns JSON for about 188 million works: journal articles, books, book chapters, reference entries, dissertations, and conference papers. Many records include an abstract, the reference list, and a citation count.

It is metadata only. It does not search full text, and it does not give access to paywalled articles.

| Task | Command |
|---|---|
| Search by topic, author, journal | `search` |
| Fetch one DOI | `work` |
| Format a citation | `cite` |
| Free-text reference → DOI | `match` |
| A work's reference list | `references` |
| Who registered a DOI | `agency` |
| Find a journal's ISSN | `journals` |

## Critical: Things Claude Won't Know Without This Skill

### `total` is not the number of relevant results

Crossref ranks by relevance and matches **any** word. `"Ming dynasty examination"` gives 330,847 results; `Ming dynasty` with facets shows *Acta Physica Sinica* as a top journal (the name "Ming"). Read the first pages only, and narrow with filters (`--type`, `--from-year`, `--issn`, `--jstor`).

Do not sort a loose query by `is-referenced-by-count` or by date: the top items will be famous papers that match one word. `--author "Kwok-leong Tang" --sort is-referenced-by-count` returns a *New England Journal of Medicine* paper first.

### Combine field queries for precise results

Field queries (`--title`, `--author`, `--container`, ...) must all match, so combining two gives a short, focused list: `--title "civil service examinations" --author Elman` → 18 results, all Elman's work on the examinations. Words are matched whole with no stemming: `--title examination --author Elman` misses every Elman title that says *examinations*. Try both forms.

### Filter the page yourself for exact titles and names

- `--phrase` keeps only items whose title contains the query as one connected phrase. `明代科舉 --phrase` → 1 of 40 items.
- `--author-match` keeps only items with an author or editor whose name contains every word of `--author`. `--author "Kwok-leong Tang"` → 2 of 20 items (the others are Leong Kwok Onn, Kwok Peng Leong, ...).
- Both filter one page after the search. Use a larger `--rows` (up to 1000) to scan more.

### CJK searches: weak recall, try English and OpenAIRE

Crossref is weak for Chinese, Japanese, and Korean terms. Expect few hits, and sometimes none.

- Crossref splits Chinese and Japanese text into single characters. `明代科舉` also matches 新时代斗争精神 (shares 代 and 科), so `total` is huge and almost all loose matches.
- When relevant records exist, they usually rank first. But there are often very few. Tests on 2026-10-26 (counting the title and `alternate_titles`):
  - `孔廟`: 0 relevant in the first 1,000 of 14,123 hits. `--title 孔廟`: 0 in 200.
  - `文廟`: 19 in the first 1,000. `孔庙`: 6.
  - Korean `문묘`: only 6 hits in all (all relevant). `석전`: 7 hits.
  - For comparison, openaire-search with a quoted phrase found 10 records with 孔廟 and 77 with 文廟.
- Many Korean, Taiwanese, Japanese, and mainland journals deposit the English title as the main `title` and the CJK title only in `alternate_titles`. So:
  1. **Search the English form too.** `--title "Confucian temple"` gave 20 relevant items in the first 100, many with a CJK alternate title (文庙, 문묘). Try romanized forms as well (`--title Munmyo` → 13 hits).
  2. **Check `alternate_titles`, not only `title`,** when you read results by eye. `--phrase` already checks both.
  3. **Use openaire-search for CJK phrases** (`search '"孔廟"'`). It does phrase matching and also covers NDL, J-STAGE, and repository records.
- `--phrase` drops a related title that splits the term (科舉‧家族‧女德：明代楊文儷), so also try the words separately (`"明代 科舉"`).
- A zero count for a CJK term in Crossref does **not** mean that no literature exists.

Coverage: Taiwanese and Hong Kong journals often use Crossref (明代研究 via Angle Publishing, *Sino-Humanitas* via HKBU), and Korean journals are well covered. **Most mainland Chinese DOIs are not in Crossref**. CNKI and ISTIC (Wanfang) register them, and many Taiwanese DOIs are registered with Airiti. For those, `work` returns nothing; run `agency` to see who registered the DOI.

### JSTOR

DOIs starting with `10.2307/` were assigned by JSTOR (3.3M works, including many book chapters). `--jstor` adds the filter `prefix:10.2307`, and each summary has `jstor_url` (`https://www.jstor.org/stable/<suffix>`). The DOI itself may now resolve to the publisher's site (10.2307/2057472 → Duke University Press). Crossref does not search JSTOR's full text.

### Citation formatting

`cite` asks Crossref to format the record in any CSL style (`chicago-author-date`, `apa`, `modern-language-association`, `harvard-cite-them-right`, ...), or as BibTeX, RIS, or CSL-JSON. The output is only as good as the deposit. CJK records often repeat the name in both given and family (`劉小龍, 劉小龍`) and have `vol. 0`. Check CJK citations before use.

### Paging and limits

- `--rows` up to 1000. `--offset` works only while offset + rows ≤ 10,000.
- To go deeper, start with `--cursor '*'` and pass back `next_cursor`. Crossref refuses a cursor together with a date sort (`published`, `issued`, ...).
- Rate limits: 1 request/s without contact email, 3/s in the "polite pool". Set `CROSSREF_MAILTO=you@example.org` to join the polite pool. It is a contact address, not a password. The script waits 1 s (0.5 s with mailto) and retries 429, 5xx, timeouts, and dropped connections (5, 10, 20 s).

## Quick Start

### CLI

```bash
export CROSSREF_MAILTO=you@example.org          # optional, faster
python scripts/crossref_api.py search "Ming dynasty examination" --type journal-article --from-year 2000
python scripts/crossref_api.py search --author Elman --container "Late Imperial China"
python scripts/crossref_api.py search --title "civil service examinations" --author Elman
python scripts/crossref_api.py search --author "Kwok-leong Tang" --author-match --rows 50
python scripts/crossref_api.py search 明代科舉 --phrase --rows 100
python scripts/crossref_api.py search "Wang Yangming" --jstor --facets type-name:5
python scripts/crossref_api.py search --issn 1086-3257 --author Elman      # inside one journal
python scripts/crossref_api.py search "Ming" --filter has-abstract:true,has-references:true
python scripts/crossref_api.py work 10.2307/2057472
python scripts/crossref_api.py cite 10.2307/2057472 --style apa
python scripts/crossref_api.py cite 10.2307/2057472 --format bibtex
python scripts/crossref_api.py match "Elman, Political, social and cultural reproduction, JAS 1991"
python scripts/crossref_api.py references 10.1215/00219118-11591159
python scripts/crossref_api.py agency 10.13471          # a prefix or a full DOI → CNKI
python scripts/crossref_api.py journals "Late Imperial China"
```

### Python

```python
from scripts.crossref_api import CrossrefAPI

cr = CrossrefAPI()                      # reads CROSSREF_MAILTO
res = cr.search("Ming examination", type="journal-article", from_year=1980, rows=20,
                filters={"has-abstract": True}, facets="container-title:10")
for w in res["items"]:
    print(w["year"], w["authors"], w["title"], w["container"], w["url"], w["jstor_url"])

cr.search(author="Elman", issn="1086-3257")                     # one journal
cr.search(author="Kwok-leong Tang", author_match=True, rows=100)
page = cr.search("Ming", cursor="*", rows=1000)                 # deep paging
page = cr.search("Ming", cursor=page["next_cursor"], rows=1000)

cr.get_work("10.2307/2057472")          # None if not in Crossref
cr.match_citation("Elman 1991 civil service examinations reproduction")  # candidates with score
cr.cite("10.2307/2057472", style="chicago-author-date")
cr.cite("10.2307/2057472", fmt="bibtex")
cr.references("10.1215/00219118-11591159")
cr.agency("10.13471")                   # 'CNKI'
cr.journals("Late Imperial China")
```

Each summary has `doi`, `type`, `title` (with subtitle), `alternate_titles`, `authors` and `editors` ("Family, Given"), `container` (journal or book), `publisher`, `issued`, `year`, `volume`, `issue`, `page`, `issn`, `isbn`, `language`, `subjects`, `abstract` (tags removed), `cited_by` (citations Crossref knows of), `reference_count`, `url` (doi.org link), `jstor_url`, `landing_page`, and `score`.

## Best Practices

1. **Verify a reference with `match`, then `work`.** The top `match` result is a guess. Compare title, authors, and year before using the DOI. Scores are not comparable across queries. For CJK references the top match is often a wrong work: in two tests on 2026-10-26, two Chinese journal references (何淑宜 2000, 黃進興 1993) both returned unrelated Taiwanese papers. `match` is also slower for long CJK strings: about 1.5–2 s per call today, and up to about 4 s per call in an earlier bulk run (English about 1 s). For a long list (2,000+ references) plan for one to two hours, and save results as you go.
2. **Narrow before you sort.** Add `--type`, years, `--issn`, or `--jstor` first. Then sorting by `is-referenced-by-count` is meaningful.
3. **Use facets to explore** (`--facets type-name:10,container-title:10,publisher-name:10`), but remember they count the loose matches too.
4. **`cited_by` is Crossref's count only.** It is usually lower than Google Scholar's and covers only citing works with deposited references.
5. **Not found is not "does not exist".** Run `agency` before you conclude that a DOI is wrong. For DOIs outside Crossref, `agency` answers from the prefix, so it shows who registers that prefix, not that this exact DOI exists. Open `https://doi.org/<doi>` to check that it resolves.

## Related Skills

- **openaire-search**: European repositories, theses, and open-access copies
- **arxiv-search**: preprints
- **alma-sru-catalogs**, **harvard-library-catalog**: find the book in a library
- **zotero-local**: save the BibTeX or RIS from `cite` into Zotero

## Resources

- `references/api_reference.md` — endpoints, field queries, filters, sorts, facets, record fields
- `scripts/crossref_api.py` — client and CLI (zero dependencies)
- `tests/test_crossref_api.py` — offline tests
- Crossref REST API docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Swagger: https://api.crossref.org/swagger-ui/index.html

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "crossref-search"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[crossref-search] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: crossref-search* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
