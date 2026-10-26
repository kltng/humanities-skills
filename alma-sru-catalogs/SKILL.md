---
name: alma-sru-catalogs
description: Search 21 research library catalogs at once through their public Alma SRU interfaces (no API key) — Michigan, Princeton, Yale, Penn, MIT, Duke, Pittsburgh, Illinois, UC Berkeley, UCLA, Toronto, Oxford (Bodleian), Cambridge, Edinburgh, Sydney, and six Taiwan universities (National Taiwan University 臺大, NCCU 政大, NCKU 成大, NSYSU 中山, NCHU 中興, CCU 中正). Use this skill whenever the user wants to find which libraries hold a book, compare holdings across universities, search UK/Canadian/Australian/Taiwanese university catalogs, compare subject headings and classification across cataloging traditions (LCSH vs Taiwan's Chinese headings), look up items at any of these libraries by title/author/subject/ISBN/OCLC/call number, or read MARC records with vernacular (880) Chinese/Japanese/Korean script. Returns call numbers, locations, availability, and online access per library.
version: 1.1.1
license: MIT
author: Kwok-leong Tang
contributors:
  - Claude
---

# Alma SRU Catalogs Skill

Search the catalogs of 21 research libraries with one script. No API key needed.

## Overview

Many research libraries run Ex Libris **Alma**, and many leave its **SRU** interface open (Search/Retrieve via URL, a library standard for searching catalogs over plain HTTP). Queries are written in **CQL** (Contextual Query Language, e.g. `alma.title="明史"`). Records come back as MARCXML; the script turns them into simple JSON with holdings.

| Key | Library | Notes |
|-----|---------|-------|
| `umich` | University of Michigan | |
| `princeton` | Princeton University | East Asian Library (`cjk` locations) |
| `yale` | Yale University | AVE has direct access links |
| `penn` | University of Pennsylvania | AVE has direct access links |
| `mit` | MIT | SRU finds far fewer records than TIMDEX; prefer **mit-timdex** |
| `duke` | Duke University | |
| `pitt` | University of Pittsburgh | |
| `uiuc` | University of Illinois Urbana-Champaign | |
| `berkeley` | UC Berkeley | East Asian Library |
| `ucla` | UCLA | East Asian Library |
| `toronto` | University of Toronto | AVE has direct access links |
| `oxford` | Bodleian Libraries, Oxford | |
| `cambridge` | Cambridge University Libraries | |
| `edinburgh` | University of Edinburgh | |
| `sydney` | University of Sydney | No AVA/AVE holdings in SRU records; slow and drops connections (one request took 143 s, the next 1.5 s) |
| `ntu` | National Taiwan University 國立臺灣大學 | Taiwan records (see below) |
| `nccu` | National Chengchi University 國立政治大學 | Taiwan records |
| `ncku` | National Cheng Kung University 國立成功大學 | Taiwan records |
| `nsysu` | National Sun Yat-sen University 國立中山大學 | Taiwan records |
| `nchu` | National Chung Hsing University 國立中興大學 | Taiwan records |
| `ccu` | National Chung Cheng University 國立中正大學 | Taiwan records |

The single-library skills **umich-library-catalog**, **princeton-library-catalog**, **yale-library-catalog** (which adds Yale LUX), and **pitt-library-catalog** use the same code.

## Critical: Things Claude Won't Know Without This Skill

### Use SRU, not the libraries' search websites

Most of these libraries' public search sites block scripts (Cloudflare, bot challenges) or forbid search URLs in `robots.txt` (Princeton, Penn). The Primo REST API needs a key. Alma SRU is open. Use the `url` in each record only as a link for people to open in a browser.

### Taiwan records are cataloged differently

The six Taiwan libraries catalog in Chinese:

- Titles, authors, and publishers are in Chinese script **without** romanized 880 pairs. Romanized searches (`Ming shi`) find very little; search in characters, and try both traditional and simplified forms.
- Subject headings come from Taiwan's **Chinese Subject Headings** (`$2 csht`), e.g. `歷史地理 -- 研究 -- 中國 -- 明代`, not LCSH. Search them in Chinese: `subject="歷史地理"`.
- Call numbers use the **Chinese classification** 中文圖書分類法 (`084 $2 ncsclt`), e.g. `626.01`, not LC.
- Records may be in Japanese too (`language=jpn`).
- Other Taiwan universities (NTHU, NYCU, NCU, NTNU, Academia Sinica) did not answer at guessed institution codes. Hong Kong's JULAC libraries answer HTTP 401: their SRU is closed.

### Holdings are in the AVA and AVE fields

- **AVA** = print copy: `$q` library name, `$c` location, `$d` call number, `$e` available/unavailable, `$t` volume summary.
- **AVE** = online copy: `$m` collection, `$t` interface (platform), `$e` Available, `$n` note, `$u` access link (Yale, Penn, Toronto).

The script returns them as `holdings.physical` and `holdings.electronic`. Keys: `holdings.physical[]` has `library`, `location`, `call_number`, `availability`, `items_total`, `items_unavailable`, `summary`; `holdings.electronic[]` has `collection`, `interface`, `availability`, `note`, `url`.

### CJK script is in 880 fields

Main fields are romanized (pinyin, Hepburn, McCune-Reischauer); the original script is in linked 880 fields. The script pairs them: `明史研究 (Ming shi yan jiu)`. Search both scripts for full coverage. Some records (e.g. some at Toronto and Oxford) have only the original script.

### Title searches match words, not phrases

- `alma.title="shi dian"` matches records with *shi* and *dian* anywhere in the title (353 hits at U-M, including a Shenyang phone book). Quotes and `adj` change nothing; `==` matches the whole title field exactly.
- Use `phrase=True` (CLI `--phrase`) to keep only titles that contain the term as one connected phrase. It filters each page after the search, so `total` is still the server's count; use `search_all(..., phrase=True)` to scan every page.
- Pinyin syllables stay ambiguous: `shi dian` also matches 知识典籍 (*zhi shi dian ji*), and `ji qi` is 機器 as well as 祭器. After a romanized search, keep the records whose vernacular title has the characters you want.
- **A CJK title search can also miss titles that contain the term.** Alma splits CJK titles into words with a dictionary: 文廟祀典考 is indexed as 文 / 廟祀 / 典考, so `alma.title="文廟"` misses it at U-M and Princeton (Yale finds it). The romanized `Wen miao` finds it.
- So never treat one CJK title search as complete. Search the traditional, simplified, and romanized forms (文廟, 文庙, Wen miao) and merge the results by `mms_id`.

### Limits and quirks

- **50 records per request** per library. `search_all()` pages for you.
- **Sort** goes inside the CQL (`sortBy alma.main_pub_date/sort.descending`); `sortKeys` is ignored. Unknown dates (`uuuu`) sort first in ascending order; add `cql="alma.main_pub_date>=1000"`.
- **Default order is not relevance ranking.** Narrow the query instead of trusting the first hits.
- **Subject headings:** write LCSH as plain words, without ` -- `, in LC's inverted form. `alma.subjects="Confucius Cult"` works; `"Confucius -- Cult"` gives 0. `"Temples, Confucian"` works; `"Confucian temples"` gives 0.
- **Network errors are retried.** Dropped connections, read timeouts, and HTTP 429/5xx are retried up to 4 times (waiting 5, 10, 20 s, or `Retry-After`). If a later page of `search_all()` still fails, it raises `IncompleteResults`; the records fetched so far are in its `.records`.
- **Unknown index names** give a vague "Catalog search has encountered an error".
- **Searching all 21 takes about 45 seconds.** Each server gets at most one request per second; different servers are queried back to back without waiting, but the six Taiwan libraries share one server (`ap01`), so they go one per second.

## When to Use

- "Which libraries have X?" / "Is there a copy of X in the UK?"
- Comparing Chinese, Japanese, or Korean holdings across East Asian collections
- Checking an OCLC number or ISBN against many libraries at once
- Getting MARC data (subjects, call numbers, identifiers) from several catalogs

## Quick Start

### CLI

```bash
python scripts/alma_sru.py libraries
python scripts/alma_sru.py search --library oxford --title 明史 --language chi --limit 5
python scripts/alma_sru.py search --library oxford,cambridge,edinburgh --oclc 424023
python scripts/alma_sru.py search --library all --isbn 9787101003277 --limit 1
python scripts/alma_sru.py search --library berkeley,ucla --cql 'alma.title=明史 and alma.main_pub_date<1900' --sort date_asc
python scripts/alma_sru.py search --library toronto --title "Ming shi" --json
python scripts/alma_sru.py search --library ntu,nccu,ccu --subject 歷史地理 --limit 3
python scripts/alma_sru.py record --library penn 9960332043503681
```

### Python

```python
from scripts.alma_sru import AlmaSRU, search_many, resolve_libraries

# One library
oxford = AlmaSRU("oxford")
result = oxford.search(title="明史", language="chi", limit=10)
for rec in result["records"]:
    print(rec["title"], rec["year"], rec["url"])
    for h in rec["holdings"]["physical"]:
        print("  ", h["library"], h["call_number"], h["availability"])

# Many libraries: {key: result}; a failing library gets {"error": ...}
results = search_many(resolve_libraries("all"), oclc="424023", limit=1)
holders = [k for k, r in results.items() if r.get("total")]

from scripts.alma_sru import IncompleteResults
try:
    records = AlmaSRU("sydney").search_all(title="kong miao", max_results=500)
except IncompleteResults as e:          # a later page failed after retries
    records = e.records                 # keep what was fetched; say the list is partial
oxford.search_all(subject="China History Ming dynasty", max_results=200)
oxford.get_record("991027744457507026")
```

Search fields: `keyword`, `title`, `author`, `subject`, `isbn`, `issn`, `oclc`, `lccn`, `publisher`, `series`, `call_number`, `language` (MARC code: `chi`, `jpn`, `kor`), `mms_id`. Sort: `date_desc`, `date_asc`, `title`, `author`.

Each summary has `mms_id`, `title`, `titles`, `author`, `authors`, `contributors`, `edition`, `publication`, `year`, `language`, `physical_description`, `series`, `subjects`, `isbns`, `oclc`, `lccn`, `lc_call_number`, `classifications`, `subject_headings`, `holdings`, and `url`. Search results also carry `library`, `total`, and `query`.

**Cataloging fields** (for comparing cataloging traditions): `subject_headings` lists each 6XX heading with its vocabulary (`lcsh`, `csht` = Taiwan's Chinese subject headings, `fast`, `mesh`, …), and `classifications` lists each class number with its scheme (`lcc`, `ddc`, `ncsclt` = 中文圖書分類法, the Chinese classification used in Taiwan, …). `subjects` stays a plain list of strings.

## Best Practices

1. **Use `oclc` or `isbn` to compare holdings.** Title searches return different editions at each library.
2. **Search both scripts** (characters and romanization).
3. **Start with a few libraries**, then widen to `all` if needed.
4. **Give people the `url`** to check live status or request items.
5. **Respect the servers.** Do not page through thousands of records.

## Related Skills

- **mit-timdex**: MIT's official API, better than SRU for MIT
- **taiwan-ldt-authorities**: look up Taiwan's name authorities, Chinese subject headings, and classification behind these records
- **harvard-library-catalog**, **columbia-clio**, **loc-catalog**: catalogs that do not use Alma SRU
- **hathitrust-catalog**: digitized copies by OCLC number
- **zotero-local**: save found records

## Resources

- `references/api_reference.md` — endpoints, how to add a library, CQL syntax, indexes, MARC and AVA/AVE guide
- `scripts/alma_sru.py` — client and CLI (zero dependencies); the `LIBRARIES` table
- `tests/test_alma_sru.py` — offline tests (`python -m unittest discover -s tests`)
- Ex Libris SRU docs: https://developers.exlibrisgroup.com/alma/integrations/sru/

## Feedback and Citation

**Report a problem.** This skill is part of the public repository [kltng/humanities-skills](https://github.com/kltng/humanities-skills). If it fails (an API changed, a script errors, or these instructions are wrong), report it as a GitHub issue:

1. Ask the user before filing. Issues are public.
2. Check for an existing report: `gh issue list --repo kltng/humanities-skills --state all --search "alma-sru-catalogs"`
3. File it: `gh issue create --repo kltng/humanities-skills --label bug --title "[alma-sru-catalogs] <short summary>" --body "<details>"`. Without `gh`, give the user this link: https://github.com/kltng/humanities-skills/issues/new?template=skill-problem.yml
4. Include the skill name and version, what you ran, the error text, what you expected, and the environment (OS, Python version). Leave out API keys, personal data, private file paths, and unpublished research.

**Cite.** If this skill helped work that is published, please cite it, together with the data source it uses:

> Tang, Kwok-leong. *humanities-skills: alma-sru-catalogs* (version <version at the top of this file>). GitHub, <year>. https://github.com/kltng/humanities-skills

When you help a user write up results that relied on this skill, remind them once about this citation.
