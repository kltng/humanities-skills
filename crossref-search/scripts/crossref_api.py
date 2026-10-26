"""
Crossref REST API client — zero external dependencies.

Crossref (https://api.crossref.org) holds metadata for 170M+ DOIs deposited
by publishers: journal articles, books, book chapters (including JSTOR's
10.2307 DOIs), conference papers, and reference lists. No API key.

Set CROSSREF_MAILTO to your email to use the faster "polite" pool
(3 requests/s instead of 1). It is a contact address, not a credential.

Usage as a CLI:
    python crossref_api.py search "Ming dynasty examination" --rows 5
    python crossref_api.py search --author Elman --container "Late Imperial China"
    python crossref_api.py search 明代科舉 --phrase --rows 50
    python crossref_api.py search "Wang Yangming" --jstor --from-year 2000
    python crossref_api.py work 10.2307/2057472
    python crossref_api.py cite 10.2307/2057472 --style chicago-author-date
    python crossref_api.py match "Elman, Political, social and cultural reproduction, JAS 1991"
    python crossref_api.py references 10.1215/00219118-11591159
    python crossref_api.py agency 10.3969/j.issn.1000-0062.2010.01.001
    python crossref_api.py journals "Late Imperial China"
"""

import argparse
import email.utils
import html
import http.client
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union

BASE_URL = "https://api.crossref.org"
DOI_RA_URL = "https://doi.org/ra"
USER_AGENT = (
    "CrossrefSearchSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills"
)

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

# Field queries accepted by /works (friendly name -> query parameter)
FIELD_QUERIES = {
    "title": "query.title",
    "author": "query.author",
    "translator": "query.translator",
    "editor": "query.editor",
    "contributor": "query.contributor",
    "container": "query.container-title",
    "publisher": "query.publisher-name",
    "affiliation": "query.affiliation",
}

SORTS = (
    "relevance", "score", "published", "issued", "published-print", "published-online",
    "is-referenced-by-count", "references-count", "created", "updated", "indexed", "deposited",
)
# Crossref refuses these sorts together with a cursor
DATE_SORTS = ("published", "issued", "published-print", "published-online")

# offset + rows must stay at or below this; use a cursor to go deeper
MAX_OFFSET = 10000

# Formats for /works/{doi}/transform (friendly name -> Accept header)
CITATION_FORMATS = {
    "text": "text/x-bibliography",
    "bibtex": "application/x-bibtex",
    "ris": "application/x-research-info-systems",
    "csl": "application/vnd.citationstyles.csl+json",
}

JSTOR_PREFIX = "10.2307"


class CrossrefError(RuntimeError):
    """Crossref rejected the request (bad filter, sort, offset, style, ...)."""


def normalize_doi(doi: str) -> str:
    """Strip 'https://doi.org/', 'doi:' and spaces from a DOI; lowercase is not needed."""
    doi = doi.strip()
    doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    return doi


def _quote_doi(doi: str) -> str:
    return urllib.parse.quote(normalize_doi(doi), safe="/")


class CrossrefAPI:
    """Client for the Crossref REST API."""

    def __init__(self, mailto: Optional[str] = None, min_interval: Optional[float] = None):
        self.mailto = mailto if mailto is not None else os.environ.get("CROSSREF_MAILTO", "")
        # Public pool allows 1 request/s; polite pool 3/s (we stay at 2/s)
        if min_interval is None:
            min_interval = 0.5 if self.mailto else 1.0
        self._min_interval = min_interval
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.time()

    @staticmethod
    def _retry_after_seconds(e: urllib.error.HTTPError, default: float) -> float:
        """Parse a Retry-After header (seconds or HTTP date), capped at 5 min."""
        value = e.headers.get("Retry-After") if e.headers else None
        if value:
            try:
                return min(300.0, max(0.0, float(value)))
            except ValueError:
                try:
                    when = email.utils.parsedate_to_datetime(value)
                    return min(300.0, max(0.0, when.timestamp() - time.time()))
                except (TypeError, ValueError, AttributeError):
                    pass
        return default

    def _request(self, url: str, accept: str = "application/json") -> str:
        """GET a URL with rate limiting and retries; return the body as text."""
        agent = USER_AGENT + (f"; mailto:{self.mailto})" if self.mailto else ")")
        req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": accept})
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code in RETRY_HTTP_CODES and attempt < MAX_ATTEMPTS - 1:
                    time.sleep(self._retry_after_seconds(e, 5.0 * 2 ** attempt))
                    continue
                if e.code in (400, 406):
                    raise CrossrefError(_error_message(e.read().decode("utf-8", "replace"))) from e
                raise
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(5.0 * 2 ** attempt)
        raise RuntimeError("unreachable")

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        if self.mailto:
            params["mailto"] = self.mailto
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        payload = json.loads(self._request(f"{BASE_URL}{path}" + (f"?{query}" if query else "")))
        if payload.get("status") != "ok":
            raise CrossrefError(_error_message(json.dumps(payload)))
        return payload["message"]

    # ── Search ──

    @staticmethod
    def build_filter(
        filters: Union[str, Dict[str, Any], None] = None,
        type: Optional[str] = None,
        from_year: Optional[Union[int, str]] = None,
        until_year: Optional[Union[int, str]] = None,
        jstor: bool = False,
    ) -> str:
        """Build Crossref's comma-separated filter string."""
        parts: List[str] = []
        if isinstance(filters, str):
            parts.extend(p for p in filters.split(",") if p)
        elif filters:
            for name, value in filters.items():
                for v in value if isinstance(value, (list, tuple)) else [value]:
                    if isinstance(v, bool):
                        v = str(v).lower()
                    parts.append(f"{name}:{v}")
        if type:
            parts.append(f"type:{type}")
        if from_year:
            parts.append(f"from-pub-date:{from_year}")
        if until_year:
            parts.append(f"until-pub-date:{until_year}")
        if jstor:
            parts.append(f"prefix:{JSTOR_PREFIX}")
        return ",".join(parts)

    def search(
        self,
        query: Optional[str] = None,
        filters: Union[str, Dict[str, Any], None] = None,
        type: Optional[str] = None,
        from_year: Optional[Union[int, str]] = None,
        until_year: Optional[Union[int, str]] = None,
        jstor: bool = False,
        sort: Optional[str] = None,
        order: str = "desc",
        rows: int = 20,
        offset: int = 0,
        cursor: Optional[str] = None,
        facets: Optional[str] = None,
        select: Optional[str] = None,
        phrase: bool = False,
        author_match: bool = False,
        raw: bool = False,
        issn: Optional[str] = None,
        **fields: Optional[str],
    ) -> Dict[str, Any]:
        """
        Search works. Returns {"total", "offset", "returned", "next_cursor", "items", "facets"?}.

        Args:
            query: Free text matched against titles, authors, venues, years
                   (Crossref's query.bibliographic)
            filters: Crossref filters, as "a:b,c:d" or {"a": "b", "has-abstract": True}
            type: Work type, e.g. journal-article, book, book-chapter, monograph
            from_year / until_year: Publication date bounds (YYYY, YYYY-MM, YYYY-MM-DD)
            jstor: Only DOIs registered by JSTOR (prefix 10.2307)
            sort: relevance (default), published, is-referenced-by-count, ...
            order: desc or asc
            rows: Results per page (max 1000)
            offset: Skip this many results (offset + rows <= 10000)
            cursor: "*" to start deep paging; then pass back `next_cursor`
            facets: Facet counts, e.g. "type-name:10,publisher-name:10"
            select: Comma-separated fields to return (raw mode only)
            phrase: Keep only items whose title contains `query` (else `title`)
                    as one phrase
            author_match: Keep only items with an author or editor whose name
                          contains every word of `author`
            raw: Return Crossref items unchanged instead of summaries
            issn: Search inside one journal (/journals/{issn}/works)
            **fields: Field queries: title, author, translator, editor,
                      contributor, container, publisher, affiliation
        """
        params: Dict[str, Any] = {"query.bibliographic": query}
        for name, value in fields.items():
            if name not in FIELD_QUERIES:
                raise ValueError(f"Unknown field query: {name}. Use one of {sorted(FIELD_QUERIES)}")
            params[FIELD_QUERIES[name]] = value
        phrase_text = query or fields.get("title")
        if phrase and not phrase_text:
            raise ValueError("phrase=True needs query or title text")
        if author_match and not fields.get("author"):
            raise ValueError("author_match=True needs author")
        if (phrase or author_match) and raw:
            raise ValueError("phrase and author_match work on summaries (raw=False)")
        if sort:
            if sort not in SORTS:
                raise ValueError(f"Unknown sort: {sort}. Use one of {SORTS}")
            if cursor and sort in DATE_SORTS:
                raise ValueError(f"Crossref cannot sort by {sort} when paging with a cursor")
            params["sort"] = sort
            params["order"] = order
        rows = max(0, min(rows, 1000))
        if cursor:
            params["cursor"] = cursor
        elif offset:
            if offset + rows > MAX_OFFSET:
                raise ValueError(f"offset + rows must be <= {MAX_OFFSET}; use cursor='*' to go deeper")
            params["offset"] = offset
        params["rows"] = rows
        params["filter"] = self.build_filter(filters, type, from_year, until_year, jstor)
        params["facet"] = facets
        params["select"] = select if raw else None

        path = f"/journals/{urllib.parse.quote(issn)}/works" if issn else "/works"
        message = self._get_json(path, params)
        items = message.get("items") or []
        result_items = items if raw else [summarize(i) for i in items]
        if phrase:
            result_items = [r for r in result_items if title_matches(r, phrase_text or "")]
        if author_match:
            result_items = [r for r in result_items if author_matches(r, fields["author"] or "")]
        result: Dict[str, Any] = {
            "total": message.get("total-results", 0),
            "offset": offset,
            "returned": len(items),
            "next_cursor": message.get("next-cursor"),
            "items": result_items,
        }
        if facets:
            result["facets"] = {
                name: list((facet.get("values") or {}).items())
                for name, facet in (message.get("facets") or {}).items()
            }
        return result

    def match_citation(self, citation: str, rows: int = 3) -> List[Dict[str, Any]]:
        """
        Find the DOI for a free-text reference. Returns the top candidates with
        Crossref's `score`. Always check title, author, and year: the top hit
        is a guess, not a match.
        """
        return self.search(citation, rows=rows)["items"]

    # ── Single works ──

    def get_work(self, doi: str, raw: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch one work by DOI. Returns None if Crossref does not have it."""
        try:
            message = self._get_json(f"/works/{_quote_doi(doi)}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        return message if raw else summarize(message)

    def references(self, doi: str) -> Optional[List[Dict[str, Any]]]:
        """
        The work's reference list, as the publisher deposited it. Returns None
        if the DOI is not in Crossref, [] if no open references were deposited.
        """
        work = self.get_work(doi, raw=True)
        if work is None:
            return None
        return [summarize_reference(r) for r in work.get("reference") or []]

    def cite(self, doi: str, style: str = "chicago-author-date", fmt: str = "text",
             locale: str = "en-US") -> str:
        """
        Format a citation. fmt is text (needs a CSL style name such as apa,
        chicago-author-date, modern-language-association), bibtex, ris, or csl.
        """
        if fmt not in CITATION_FORMATS:
            raise ValueError(f"Unknown format: {fmt}. Use one of {sorted(CITATION_FORMATS)}")
        accept = CITATION_FORMATS[fmt]
        if fmt == "text":
            accept += f"; style={style}; locale={locale}"
        try:
            return self._request(f"{BASE_URL}/works/{_quote_doi(doi)}/transform", accept=accept).strip()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise CrossrefError(f"{normalize_doi(doi)} is not in Crossref; try agency()") from e
            raise

    def agency(self, doi: str) -> str:
        """
        Which registration agency issued a DOI: Crossref, DataCite, CNKI,
        ISTIC, Airiti, JaLC, mEDRA, ... Only Crossref DOIs have metadata here.
        """
        try:
            message = self._get_json(f"/works/{_quote_doi(doi)}/agency")
            return message["agency"]["label"]
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        # Not known to Crossref: ask the DOI Foundation
        data = json.loads(self._request(f"{DOI_RA_URL}/{_quote_doi(doi)}"))
        entry = data[0] if data else {}
        return entry.get("RA") or entry.get("status", "unknown")

    # ── Journals ──

    def journals(self, query: str, rows: int = 10) -> List[Dict[str, Any]]:
        """Find journals by title. Use the ISSN with search(issn=...)."""
        message = self._get_json("/journals", {"query": query, "rows": max(1, min(rows, 1000))})
        return [summarize_journal(j) for j in message.get("items") or []]

    def journal(self, issn: str) -> Optional[Dict[str, Any]]:
        """Fetch one journal by ISSN."""
        try:
            return summarize_journal(self._get_json(f"/journals/{urllib.parse.quote(issn)}"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise


def _error_message(body: str) -> str:
    """Pull the readable message out of a Crossref error body."""
    try:
        payload = json.loads(body)
    except ValueError:
        return body.strip()[:500]
    message = payload.get("message", payload)
    if isinstance(message, list):
        return "; ".join(m.get("message", str(m)) for m in message)
    return str(message)[:500]


# ── Phrase and author matching ──

_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")


def _normalize(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse spaces (CJK kept)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def title_matches(record: Dict[str, Any], term: str) -> bool:
    """True if `term` is one connected phrase in the title or an alternate title."""
    needle = _normalize(term)
    if not needle:
        return False
    cjk = bool(_CJK.search(needle))
    for text in [record.get("title") or ""] + list(record.get("alternate_titles") or []):
        hay = _normalize(text)
        if cjk and needle.replace(" ", "") in hay.replace(" ", ""):
            return True
        if not cjk and f" {needle} " in f" {hay} ":
            return True
    return False


def author_matches(record: Dict[str, Any], name: str) -> bool:
    """True if one author or editor name contains every word of `name`."""
    words = _normalize(name).replace("-", " ").split()
    if not words:
        return False
    for person in list(record.get("authors") or []) + list(record.get("editors") or []):
        hay = _normalize(person).replace("-", " ")
        if _CJK.search(hay):
            if "".join(words) in hay.replace(" ", ""):
                return True
        elif all(w in hay.split() for w in words):
            return True
    return False


# ── Summarizing ──

def _first(values: Any) -> str:
    if isinstance(values, list):
        return values[0] if values else ""
    return values or ""


def _date(parts: Any) -> str:
    """Turn {'date-parts': [[2024, 12, 1]]} into '2024-12-01'."""
    try:
        numbers = (parts or {}).get("date-parts", [[]])[0]
    except (AttributeError, IndexError, TypeError):
        return ""
    numbers = [n for n in numbers or [] if n is not None]
    if not numbers:
        return ""
    return "-".join([str(numbers[0])] + [f"{n:02d}" for n in numbers[1:]])


def _person(p: Dict[str, Any]) -> str:
    """'Family, Given', or the organization name. Repeated names are shown once."""
    if p.get("name"):
        return p["name"]
    family, given = p.get("family", ""), p.get("given", "")
    if given and given != family:
        return f"{family}, {given}" if family else given
    return family or given


def clean_abstract(text: str) -> str:
    """Strip JATS XML tags from a Crossref abstract."""
    text = re.sub(r"<jats:title>.*?</jats:title>", " ", text or "", flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def summarize(item: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a Crossref work into a clean dict."""
    doi = item.get("DOI", "")
    title = _first(item.get("title"))
    subtitle = _first(item.get("subtitle"))
    if subtitle and subtitle.lower() not in title.lower():
        title = f"{title}: {subtitle}" if title else subtitle
    isbns = item.get("ISBN") or [i.get("value") for i in item.get("isbn-type") or []]
    issued = _date(item.get("issued"))
    return {
        "doi": doi,
        "type": item.get("type", ""),
        "title": title,
        "alternate_titles": list(dict.fromkeys(
            (item.get("original-title") or []) + (item.get("short-title") or []))),
        "authors": [_person(a) for a in item.get("author") or []],
        "editors": [_person(a) for a in item.get("editor") or []],
        "container": _first(item.get("container-title")),
        "publisher": item.get("publisher", ""),
        "issued": issued,
        "year": issued[:4],
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "page": item.get("page", ""),
        "issn": list(dict.fromkeys(item.get("ISSN") or [])),
        "isbn": list(dict.fromkeys(i for i in isbns if i)),
        "language": item.get("language", ""),
        "subjects": item.get("subject") or [],
        "abstract": clean_abstract(item.get("abstract", "")),
        "cited_by": item.get("is-referenced-by-count", 0),
        "reference_count": item.get("references-count", item.get("reference-count", 0)),
        "url": f"https://doi.org/{doi}" if doi else "",
        "jstor_url": jstor_url(doi),
        "landing_page": ((item.get("resource") or {}).get("primary") or {}).get("URL", ""),
        "score": item.get("score"),
    }


def jstor_url(doi: str) -> str:
    """JSTOR stable URL for a JSTOR-registered DOI (prefix 10.2307), else ''."""
    if doi.lower().startswith(JSTOR_PREFIX + "/"):
        return f"https://www.jstor.org/stable/{doi.split('/', 1)[1]}"
    return ""


def summarize_reference(ref: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize one entry of a work's reference list."""
    title = ref.get("article-title") or ref.get("volume-title") or ref.get("series-title") or ""
    return {
        "doi": ref.get("DOI", ""),
        "doi_asserted_by": ref.get("doi-asserted-by", ""),
        "author": ref.get("author", ""),
        "year": ref.get("year", ""),
        "title": title,
        "container": ref.get("journal-title", ""),
        "unstructured": ref.get("unstructured", ""),
    }


def summarize_journal(j: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": j.get("title", ""),
        "publisher": j.get("publisher", ""),
        "issn": j.get("ISSN") or [],
        "subjects": [s.get("name") for s in j.get("subjects") or [] if s.get("name")],
        "dois": (j.get("counts") or {}).get("total-dois", 0),
    }


# ── CLI ──

def _print_summary(rec: Dict[str, Any]) -> None:
    print(rec["title"] or "(no title)")
    if rec["authors"] or rec["editors"]:
        names = rec["authors"] or [f"{e} (ed.)" for e in rec["editors"]]
        print(f"  By: {'; '.join(names[:4])}" + (" et al." if len(names) > 4 else ""))
    where = ", ".join(p for p in (rec["container"], rec["publisher"]) if p)
    vol = " ".join(p for p in (rec["volume"] and f"vol. {rec['volume']}",
                               rec["issue"] and f"no. {rec['issue']}",
                               rec["page"] and f"pp. {rec['page']}") if p)
    print(f"  {rec['type']}  {rec['issued']}  {where}" + (f"  {vol}" if vol else ""))
    print(f"  Cited by {rec['cited_by']}  {rec['url']}" + (f"  JSTOR: {rec['jstor_url']}" if rec["jstor_url"] else ""))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search Crossref DOI metadata.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search works")
    s.add_argument("query", nargs="?", help="Free text (query.bibliographic)")
    for name in FIELD_QUERIES:
        s.add_argument(f"--{name}", help=f"Field query ({FIELD_QUERIES[name]})")
    s.add_argument("--filter", help="Crossref filters, e.g. has-abstract:true,type:book")
    s.add_argument("--type", help="journal-article, book, book-chapter, monograph, ...")
    s.add_argument("--from-year")
    s.add_argument("--until-year")
    s.add_argument("--jstor", action="store_true", help="Only JSTOR DOIs (prefix 10.2307)")
    s.add_argument("--issn", help="Search inside one journal")
    s.add_argument("--sort", choices=SORTS)
    s.add_argument("--order", choices=("asc", "desc"), default="desc")
    s.add_argument("--rows", type=int, default=10)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--cursor", help="'*' to start deep paging, then the next_cursor value")
    s.add_argument("--facets", help="e.g. type-name:10,publisher-name:10,container-title:10")
    s.add_argument("--phrase", action="store_true", help="Keep only titles containing the query as one phrase")
    s.add_argument("--author-match", action="store_true", help="Keep only items with a name containing every --author word")
    s.add_argument("--json", action="store_true")

    w = sub.add_parser("work", help="Fetch one work by DOI")
    w.add_argument("doi")
    w.add_argument("--raw", action="store_true", help="Print the Crossref record unchanged")

    c = sub.add_parser("cite", help="Format a citation for a DOI")
    c.add_argument("doi")
    c.add_argument("--style", default="chicago-author-date", help="CSL style name, e.g. apa, modern-language-association")
    c.add_argument("--format", dest="fmt", choices=sorted(CITATION_FORMATS), default="text")
    c.add_argument("--locale", default="en-US")

    m = sub.add_parser("match", help="Find candidate DOIs for a free-text reference")
    m.add_argument("citation")
    m.add_argument("--rows", type=int, default=3)

    r = sub.add_parser("references", help="List a work's deposited references")
    r.add_argument("doi")

    a = sub.add_parser("agency", help="Which agency registered a DOI")
    a.add_argument("doi")

    j = sub.add_parser("journals", help="Find journals by title")
    j.add_argument("query")
    j.add_argument("--rows", type=int, default=10)

    args = parser.parse_args(argv)
    api = CrossrefAPI()

    if args.command == "search":
        fields = {n: getattr(args, n) for n in FIELD_QUERIES if getattr(args, n)}
        result = api.search(
            args.query, filters=args.filter, type=args.type, from_year=args.from_year,
            until_year=args.until_year, jstor=args.jstor, issn=args.issn, sort=args.sort,
            order=args.order, rows=args.rows, offset=args.offset, cursor=args.cursor,
            facets=args.facets, phrase=args.phrase, author_match=args.author_match, **fields)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print(f"{result['total']} results (relevance-ranked; most of a large total is loose matches)\n")
        if args.phrase or args.author_match:
            print(f"{len(result['items'])} of {result['returned']} items on this page passed the filter\n")
        for name, values in result.get("facets", {}).items():
            print(f"  {name}: " + ", ".join(f"{k} ({n})" for k, n in values))
        if result.get("facets"):
            print()
        for rec in result["items"]:
            _print_summary(rec)
            print()
        if result["next_cursor"] and args.cursor:
            print(f"next cursor: {result['next_cursor']}")
        return 0

    if args.command == "work":
        rec = api.get_work(args.doi, raw=args.raw)
        if rec is None:
            print(f"{args.doi} is not in Crossref (registered by: {api.agency(args.doi)})", file=sys.stderr)
            return 1
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    elif args.command == "cite":
        print(api.cite(args.doi, style=args.style, fmt=args.fmt, locale=args.locale))
    elif args.command == "match":
        for rec in api.match_citation(args.citation, rows=args.rows):
            print(f"score {rec['score']}")
            _print_summary(rec)
            print()
    elif args.command == "references":
        refs = api.references(args.doi)
        if refs is None:
            print(f"{args.doi} is not in Crossref", file=sys.stderr)
            return 1
        print(json.dumps(refs, ensure_ascii=False, indent=2))
    elif args.command == "agency":
        print(api.agency(args.doi))
    else:
        print(json.dumps(api.journals(args.query, rows=args.rows), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
