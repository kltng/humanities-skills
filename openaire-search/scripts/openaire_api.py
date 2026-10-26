"""
OpenAIRE Graph API client — zero external dependencies.

OpenAIRE (https://graph.openaire.eu) merges records from Crossref, DataCite,
ORCID, and thousands of institutional repositories into one graph of
research products (publications, datasets, software, other), projects,
organizations, and data sources. It is strong on theses, repository copies,
and open-access versions. No API key; an access token raises the limit.

Usage as a CLI:
    python openaire_api.py search "Ming dynasty" --type publication --rows 5
    python openaire_api.py search 明代科舉 --phrase
    python openaire_api.py search "Ming dynasty" --instance-type "Doctoral thesis" --open
    python openaire_api.py search --author "Kwok-leong Tang"
    python openaire_api.py doi 10.2307/2057472
    python openaire_api.py get doi_dedup___::5619fd1bdb39d6549898d1c1583fcdea
    python openaire_api.py datasources "HKU Scholars Hub"
    python openaire_api.py organizations "Academia Sinica"
    python openaire_api.py projects "Ming"
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
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union

BASE_URL = "https://api.openaire.eu/graph/v3"
USER_AGENT = (
    "OpenAIRESearchSkill/1.0 (Claude Code skill; research use; "
    "+https://github.com/kltng/humanities-skills)"
)

# Attempts per request; waits between them are 5, 10, 20 s (or Retry-After)
MAX_ATTEMPTS = 4
RETRY_HTTP_CODES = (429, 500, 502, 503, 504)
NETWORK_ERRORS = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException)

ENTITIES = ("research-products", "projects", "organizations", "datasources", "persons")

# Friendly names for research-product parameters (friendly -> API parameter)
PRODUCT_PARAMS = {
    "title": "mainTitle",
    "description": "description",
    "author": "authorFullName",
    "author_id": "authorId",
    "type": "type",
    "instance_type": "instanceType",
    "access": "accessRightLabel",
    "language": "language",
    "country": "countryCode",
    "subjects": "subjects",
    "fos": "fos",
    "publisher": "publisher",
    "pid": "pid",
    "organization": "relOrganization",
    "datasource": "relHostingDataSource",
    "datasource_id": "relHostingDataSourceId",
    "source": "source",
    "project": "relProject",
    "funder": "relFunder",
    "from_date": "fromPublicationDate",
    "to_date": "toPublicationDate",
    "peer_reviewed": "isPeerReviewed",
    "oa_color": "openAccessColor",
}

SORT_FIELDS = ("relevance", "publicationDate", "dateOfCollection", "influence",
               "popularity", "citationCount", "impulse")

# page * page_size must stay at or below this; use a cursor to go deeper
MAX_RESULTS_BY_PAGE = 10000

# Parameters that take free text or numbers and must not be auto-quoted
_UNQUOTED = {"search", "fromPublicationDate", "toPublicationDate", "fromPublicationYear",
             "toPublicationYear", "page", "pageSize", "cursor", "sortBy", "logicalOperator"}
_OPERATOR = re.compile(r"\b(AND|OR|NOT)\b")


class OpenAIREError(RuntimeError):
    """OpenAIRE rejected the request (bad value, page too deep, ...)."""


def quote_value(value: str) -> str:
    """
    Wrap a filter value in double quotes when it has spaces or parentheses,
    as OpenAIRE requires (accessRightLabel="Open Access"). Values that
    already contain quotes or AND/OR/NOT are left alone.
    """
    if '"' in value or _OPERATOR.search(value):
        return value
    if re.search(r"[\s()]", value):
        return f'"{value}"'
    return value


class OpenAIREAPI:
    """Client for the OpenAIRE Graph API (v3)."""

    def __init__(self, token: Optional[str] = None, min_interval: float = 1.0):
        # Personal access token from https://develop.openaire.eu (valid one hour)
        self.token = token if token is not None else os.environ.get("OPENAIRE_ACCESS_TOKEN", "")
        self._min_interval = min_interval
        self._last_request = 0.0
        self.rate_limit: Dict[str, str] = {}

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

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        for attempt in range(MAX_ATTEMPTS):
            self._rate_limit()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self.rate_limit = {
                        k.lower(): v for k, v in resp.headers.items() if k.lower().startswith("x-ratelimit")
                    } if resp.headers else {}
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in RETRY_HTTP_CODES and attempt < MAX_ATTEMPTS - 1:
                    time.sleep(self._retry_after_seconds(e, 5.0 * 2 ** attempt))
                    continue
                if e.code == 400:
                    raise OpenAIREError(_error_message(e.read().decode("utf-8", "replace"))) from e
                raise
            except NETWORK_ERRORS:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                time.sleep(5.0 * 2 ** attempt)
        raise RuntimeError("unreachable")

    # ── Search ──

    @staticmethod
    def build_params(
        search: Optional[str] = None,
        phrase: bool = False,
        entity: str = "research-products",
        open_access: bool = False,
        sort: Optional[str] = None,
        order: str = "DESC",
        page: int = 1,
        page_size: int = 10,
        cursor: Optional[str] = None,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Map friendly names to OpenAIRE parameters and quote values as needed."""
        if entity not in ENTITIES:
            raise ValueError(f"Unknown entity: {entity}. Use one of {ENTITIES}")
        params: Dict[str, Any] = {}
        if search:
            params["search"] = f'"{search}"' if phrase and '"' not in search else search
        elif phrase:
            raise ValueError("phrase=True needs search text")
        if open_access:
            filters["access"] = "Open Access"
        for name, value in filters.items():
            if value in (None, ""):
                continue
            key = PRODUCT_PARAMS.get(name, name) if entity == "research-products" else name
            if isinstance(value, bool):
                value = str(value).lower()
            elif key not in _UNQUOTED:
                value = quote_value(str(value))
            params[key] = value
        if not params:
            raise ValueError("Give search text or at least one filter")
        if sort:
            if sort not in SORT_FIELDS:
                raise ValueError(f"Unknown sort: {sort}. Use one of {SORT_FIELDS}")
            if cursor:
                raise ValueError("OpenAIRE ignores sort when paging with a cursor")
            params["sortBy"] = f"{sort} {order.upper()}"
        page_size = max(1, min(page_size, 100))
        if cursor:
            params["cursor"] = cursor
        else:
            if page * page_size > MAX_RESULTS_BY_PAGE:
                raise ValueError(f"page * page_size must be <= {MAX_RESULTS_BY_PAGE}; use cursor='*' to go deeper")
            params["page"] = page
        params["pageSize"] = page_size
        return params

    def search(
        self,
        search: Optional[str] = None,
        entity: str = "research-products",
        phrase: bool = False,
        open_access: bool = False,
        sort: Optional[str] = None,
        order: str = "DESC",
        page: int = 1,
        page_size: int = 10,
        cursor: Optional[str] = None,
        raw: bool = False,
        **filters: Any,
    ) -> Dict[str, Any]:
        """
        Search an entity. Returns {"total", "page", "next_cursor", "items"}.

        Args:
            search: Keywords. Words are matched loosely; use phrase=True or
                    put the phrase in double quotes for an exact phrase.
                    AND, OR, NOT (uppercase) and parentheses work.
            entity: research-products (default), projects, organizations,
                    datasources, persons
            phrase: Wrap `search` in double quotes (exact phrase; best for CJK)
            open_access: Only products whose best access right is Open Access
            sort: relevance, publicationDate, citationCount, influence, popularity, ...
            order: DESC or ASC
            page / page_size: 1-based page; page_size up to 100; page * page_size <= 10000
            cursor: "*" to start deep paging, then pass back `next_cursor`
                    (results then come in a fixed internal order)
            raw: Return OpenAIRE records unchanged instead of summaries
            **filters: For research products: title, description, author,
                       author_id, type (publication, dataset, software, other),
                       instance_type ("Doctoral thesis", "Article", ...),
                       access, language, country, subjects, fos, publisher,
                       pid (a DOI), organization, datasource_id (a repository's
                       OpenAIRE ID; name filters returned nothing in tests),
                       source, project, funder, from_date, to_date,
                       peer_reviewed, oa_color — or any API parameter name.
                       For other entities: the API parameter names.
        """
        params = self.build_params(search, phrase, entity, open_access, sort, order,
                                   page, page_size, cursor, **filters)
        data = self._get_json(f"/{entity}", params)
        header = data.get("header") or {}
        results = data.get("results") or []
        if not raw:
            summarizer = SUMMARIZERS[entity]
            results = [summarizer(r) for r in results]
        return {
            "total": header.get("numFound", 0),
            "page": header.get("page"),
            "next_cursor": header.get("nextCursor"),
            "items": results,
        }

    def get(self, openaire_id: str, entity: str = "research-products",
            raw: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch one record by OpenAIRE ID. Returns None if not found."""
        if entity not in ENTITIES:
            raise ValueError(f"Unknown entity: {entity}. Use one of {ENTITIES}")
        try:
            record = self._get_json(f"/{entity}/{urllib.parse.quote(openaire_id, safe=':')}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        return record if raw else SUMMARIZERS[entity](record)

    def find_doi(self, doi: str, raw: bool = False) -> Optional[Dict[str, Any]]:
        """
        Look up a DOI. The summary lists every copy OpenAIRE knows
        (publisher, repositories) with its access right, and `open_urls`.
        """
        doi = re.sub(r"^(https?://)?(dx\.)?doi\.org/|^doi:\s*", "", doi.strip(), flags=re.I)
        items = self.search(pid=doi, page_size=1, raw=raw)["items"]
        return items[0] if items else None


def _error_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except ValueError:
        return body.strip()[:500]
    return str(payload.get("message") or payload)[:500].strip()


# ── Summarizing ──

def _clean(text: str) -> str:
    """Strip JATS/HTML tags and collapse spaces."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(html.unescape(text).split())


def _fix_url(url: str) -> str:
    """Repair doubled prefixes (https://doi.org/https://doi.org/10....) and use https://doi.org/."""
    url = re.sub(r"^(https?://(dx\.)?doi\.org/)+(?=https?://)", "", url or "")
    return re.sub(r"^https?://(dx\.)?doi\.org/", "https://doi.org/", url, flags=re.I)


def _doi_from_url(url: str) -> str:
    """Return the DOI in a https://doi.org/10.... URL, or ''."""
    m = re.match(r"^https://doi\.org/(10\.\d{4,9}/\S+)$", url or "", flags=re.I)
    return urllib.parse.unquote(m.group(1)) if m else ""


def summarize_product(r: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a research product into a clean dict."""
    pids: Dict[str, List[str]] = {}
    for p in r.get("pids") or []:
        pids.setdefault(p.get("scheme", "other"), []).append(p.get("value", ""))
    copies: List[Dict[str, str]] = []
    by_url: Dict[str, Dict[str, str]] = {}
    for inst in r.get("instances") or []:
        for url in inst.get("urls") or []:
            url = _fix_url(url)
            if not url:
                continue
            copy = {
                "url": url,
                "type": inst.get("type", ""),
                "hosted_by": (inst.get("hostedBy") or {}).get("value", ""),
                "access": (inst.get("accessRight") or {}).get("label", ""),
                "license": inst.get("license") or "",
            }
            known = by_url.get(url.lower())
            if known is None:
                by_url[url.lower()] = copy
                copies.append(copy)
            elif copy["access"] == "OPEN" and known["access"] != "OPEN":
                # Same URL listed twice: keep the more informative entry
                known.update(copy)
    container = r.get("container") or {}
    pages = "-".join(p for p in (container.get("sp"), container.get("ep")) if p)
    indicators = ((r.get("indicators") or {}).get("citationImpact") or {})
    citations = indicators.get("citationCount")
    descriptions = [_clean(d) for d in r.get("descriptions") or [] if d]
    # Some records (NDL 10.11501, NIJL 10.20730, ...) have no DOI pid, only a doi.org copy URL
    doi = (pids.get("doi") or [""])[0] or next(
        (d for d in (_doi_from_url(c["url"]) for c in copies) if d), "")
    return {
        "id": r.get("id", ""),
        "type": r.get("type", ""),
        "instance_types": list(dict.fromkeys(i["type"] for i in r.get("instances") or [] if i.get("type"))),
        "title": r.get("mainTitle") or "",
        "subtitle": r.get("subTitle") or "",
        "other_titles": r.get("otherTitles") or [],
        "authors": [a.get("fullName", "") for a in r.get("authors") or [] if a.get("fullName")],
        "publication_date": r.get("publicationDate") or "",
        "year": (r.get("publicationDate") or "")[:4],
        "publisher": r.get("publisher") or "",
        "container": container.get("name") or "",
        "volume": container.get("vol") or "",
        "issue": container.get("iss") or "",
        "pages": pages,
        "language": (r.get("language") or {}).get("label", ""),
        "pids": pids,
        "doi": doi,
        "access": (r.get("bestAccessRight") or {}).get("label", ""),
        "oa_color": r.get("openAccessColor") or "",
        "is_green": bool(r.get("isGreen")),
        "subjects": [((s.get("subject") or {}).get("value", "")) for s in r.get("subjects") or []],
        "description": descriptions[0][:1000] if descriptions else "",
        "citation_count": int(citations) if citations is not None else None,
        "copies": copies,
        "open_urls": [c["url"] for c in copies if c["access"] == "OPEN"],
        "collected_from": [c.get("value", "") for c in r.get("collectedFrom") or []],
    }


def summarize_organization(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id", ""),
        "name": r.get("legalName") or "",
        "short_name": r.get("legalShortName") or "",
        "alternative_names": r.get("alternativeNames") or [],
        "country": (r.get("country") or {}).get("label", ""),
        "website": r.get("websiteUrl") or "",
        "pids": [f"{p.get('scheme')}:{p.get('value')}" for p in r.get("pids") or []],
    }


def summarize_datasource(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id", ""),
        "name": r.get("officialName") or "",
        "english_name": r.get("englishName") or "",
        "type": (r.get("type") or {}).get("value", ""),
        "website": r.get("websiteUrl") or "",
        "languages": r.get("languages") or [],
        "subjects": r.get("subjects") or [],
    }


def summarize_project(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id", ""),
        "title": r.get("title") or "",
        "acronym": r.get("acronym") or "",
        "code": r.get("code") or "",
        "start": r.get("startDate") or "",
        "end": r.get("endDate") or "",
        "funders": [f.get("shortName") or f.get("name", "") for f in r.get("fundings") or []],
        "website": r.get("websiteUrl") or "",
        "summary": _clean(r.get("summary") or "")[:1000],
    }


def summarize_person(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": r.get("id", ""),
        "given_name": r.get("givenName") or "",
        "family_name": r.get("familyName") or r.get("lastName") or "",
        "pids": [f"{p.get('scheme')}:{p.get('value')}" for p in r.get("pids") or []],
    }


SUMMARIZERS = {
    "research-products": summarize_product,
    "projects": summarize_project,
    "organizations": summarize_organization,
    "datasources": summarize_datasource,
    "persons": summarize_person,
}


# ── CLI ──

def _print_product(rec: Dict[str, Any]) -> None:
    print(rec["title"] + (f": {rec['subtitle']}" if rec["subtitle"] else ""))
    if rec["authors"]:
        print(f"  By: {'; '.join(rec['authors'][:4])}" + (" et al." if len(rec["authors"]) > 4 else ""))
    where = ", ".join(p for p in (rec["container"], rec["publisher"]) if p)
    print(f"  {', '.join(rec['instance_types'][:2]) or rec['type']}  {rec['publication_date']}  {where}")
    print(f"  Access: {rec['access'] or 'unknown'}  DOI: {rec['doi'] or '-'}  ID: {rec['id']}")
    for c in rec["copies"][:4]:
        print(f"    [{c['access'] or '?'}] {c['hosted_by']}: {c['url']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search the OpenAIRE Graph.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search research products")
    s.add_argument("search", nargs="?", help="Keywords (AND/OR/NOT, \"phrases\")")
    for name in PRODUCT_PARAMS:
        s.add_argument(f"--{name.replace('_', '-')}", dest=name)
    s.add_argument("--phrase", action="store_true", help="Search the words as one exact phrase")
    s.add_argument("--open", action="store_true", help="Only Open Access products")
    s.add_argument("--sort", choices=SORT_FIELDS)
    s.add_argument("--order", choices=("DESC", "ASC"), default="DESC")
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--rows", type=int, default=10)
    s.add_argument("--cursor")
    s.add_argument("--json", action="store_true")

    d = sub.add_parser("doi", help="Look up a DOI and list its copies")
    d.add_argument("doi")

    g = sub.add_parser("get", help="Fetch a record by OpenAIRE ID")
    g.add_argument("id")
    g.add_argument("--entity", choices=ENTITIES, default="research-products")
    g.add_argument("--raw", action="store_true")

    for name in ("organizations", "datasources", "projects", "persons"):
        e = sub.add_parser(name, help=f"Search {name}")
        e.add_argument("search")
        e.add_argument("--rows", type=int, default=10)

    args = parser.parse_args(argv)
    api = OpenAIREAPI()

    if args.command == "search":
        filters = {n: getattr(args, n) for n in PRODUCT_PARAMS if getattr(args, n)}
        result = api.search(args.search, phrase=args.phrase, open_access=args.open, sort=args.sort,
                            order=args.order, page=args.page, page_size=args.rows,
                            cursor=args.cursor, **filters)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print(f"{result['total']} results\n")
        for rec in result["items"]:
            _print_product(rec)
            print()
        if result["next_cursor"]:
            print(f"next cursor: {result['next_cursor']}")
        return 0

    if args.command == "doi":
        rec = api.find_doi(args.doi)
        if rec is None:
            print(f"{args.doi} is not in OpenAIRE", file=sys.stderr)
            return 1
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    elif args.command == "get":
        rec = api.get(args.id, entity=args.entity, raw=args.raw)
        if rec is None:
            print(f"No {args.entity} record {args.id}", file=sys.stderr)
            return 1
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        result = api.search(args.search, entity=args.command, page_size=args.rows)
        print(f"{result['total']} results")
        print(json.dumps(result["items"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
