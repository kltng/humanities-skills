# CBETA API and DILA authority API: reference

Checked live on 2026-11-09 (CBETA API version 4.6.11). Examples show real responses, shortened.

## 1. CBETA API

Base: `https://cbdata.dila.edu.tw/stable/` (GET, JSON, UTF-8). Documentation pages: `https://cbdata.dila.edu.tw/stable/static_pages/<name>` (Chinese).

Common rules:
- `q` is at most 40 characters (50 for `search/sc`). Longer → error.
- Errors: HTTP 200 with `{"success": false, "error": "缺少必要參數： work 佛典編號"}`.
- Paging: `rows` (default 20), `start` (default 0).
- `callback=<name>` wraps the answer as JSONP (not needed from Python).

### Canon IDs (search order)

T 大正藏 · X 卍續藏 · A 金藏 · K 高麗藏 · S 宋藏遺珍 · F 房山石經 · C 中華藏 · D 國圖善本 · U 洪武南藏 · P 永樂北藏 · J 嘉興藏 · L 乾隆藏 · G 佛教大藏經 · M 卍正藏 · N 南傳大藏經 · ZS 正史佛教資料類編 · I 佛教石刻拓片百品 · ZW 藏外佛教文獻 · B 大藏經補編 · GA/GB 中國佛寺志 · Y 印順法師佛學著作集 · LC 呂澂佛學著作集

### Works

| Endpoint | Purpose |
|---|---|
| `works?work=T0235` | one work's metadata |
| `works?creator_id=A001583` | works by a DILA person ID |
| `works?creator=空海` | creator name contains (all records) |
| `works?creator_name=竺` | only records whose creator has no ID yet |
| `works?dynasty=唐` / `works?dynasty=符秦,前秦` | by dynasty |
| `works?time_start=600&time_end=700` | by CE year range |
| `works?canon=T&vol_start=1&vol_end=2` | by volume range |
| `works?canon=T&work_start=1&work_end=2` | by number range |
| `works/toc?work=T0001` | internal table of contents (`title`, `juan`, `lb`, `children`) |

Work fields: `work`, `canon`, `vol`, `title`, `category` (CBETA 部類), `orig_category`, `byline`, `creators`, `creators_with_id` (`鳩摩羅什(A001583)`; several joined by `;`), `time_dynasty`, `time_from`, `time_to`, `juan` (number of fascicles), `juan_list`, `cjk_chars`, `en_words`, `file`, `places` (`[{name, id, latitude, longitude}]`), `uuid`.

```json
{"work":"T0235","vol":"T08","title":"金剛般若波羅蜜經","byline":"後秦 鳩摩羅什譯",
 "creators_with_id":"鳩摩羅什(A001583)","time_dynasty":"後秦","time_from":402,"time_to":412,
 "places":[{"name":"草堂寺","id":"PL000000042657","latitude":34.014462,"longitude":108.739486}]}
```

`time_dynasty` is `"unknown"` for many non-Chinese works, even when `time_from` is set.

### Catalogs

`catalog_entry?q=root` → `CBETA` (部類目錄) and `orig` (原書目錄). Then `catalog_entry?q=CBETA`, `catalog_entry?q=CBETA.001`, `catalog_entry?q=orig-T`… Nodes have `n`, `label`, and for leaves `work`, `juan_start`, `juan_end`. `node_type: "alt"` = CBETA has no text; it points to another canon's copy.

Category names (for the `category` filter): 本緣部類 阿含部類 般若部類 法華部類 華嚴部類 寶積部類 涅槃部類 大集部類 經集部類 密教部類 律部類 毘曇部類 中觀部類 瑜伽部類 論集部類 淨土宗部類 禪宗部類 史傳部類 事彙部類 敦煌寫本部類 國圖善本部類 南傳大藏經部類 新編部類

### Text

| Endpoint | Purpose |
|---|---|
| `juans?work=T0001&juan=1` | HTML of one fascicle (`results[0]`). `&work_info=1` adds metadata, `&toc=1` adds the TOC |
| `lines?linehead=T01n0001_p0001a04` | one line; add `before=2&after=3` |
| `lines?linehead_start=…&linehead_end=…` | a range (may cross fascicles) |
| `juans/goto?linehead=<citation>` | resolve a citation to `{work, juan, vol, lb, linehead, title}` |
| `juans/goto?canon=T&work=1&juan=2` / `&page=11&col=b&line=10` | by structure |
| `juans/goto?canon=T&vol=1&page=12` | by volume and page |

`lines` returns `{"linehead": "...", "html": "...", "notes": {"0001002": "〔長安〕－【宋】"}}`. Empty `html` = blank line.

`goto` accepts: a linehead (`T01n0001_p0066c25`); `CBETA, T01, no. 1, p. 67, a13`; `CBETA 2019.Q3, T30, no. 1579, p. 279a7`; `T51, no. 2087, pp. 868-888`; `《大正藏》冊47，第1969 號`; quick codes `DA1`, `SA`, `MA`, `EA`, `SN1.1`, `MN`, `DN`, `AN` (full list: https://github.com/DILA-edu/cbeta-metadata/blob/master/goto/goto-list.txt).

Linehead anatomy: `T08n0235_p0748c17` = canon T, vol 08, no. 0235, page 0748, column c, line 17.

### Search

| Endpoint | Purpose |
|---|---|
| `search?q=` | full text; one result per fascicle with `term_hits` |
| `search/all_in_one?q=` | same plus `kwics` per fascicle; `around` (default 10), `facet=1`, `note=0` (exclude interlinear notes) |
| `search/extended?q=` | AND `"a" "b"`, OR `"a" \| "b"`, NOT `"a" !"b"`, NEAR `"a" NEAR/7 "b"` (quotes required) |
| `search/kwic?work=&juan=&q=` | inside one fascicle (work and juan required); `mark=1`; `sort=f\|b\|location`; `negative_lookahead=弗`, `negative_lookbehind=正` |
| `search/title?q=` | fuzzy title search, at least 3 characters match |
| `search/toc?q=` | catalogs + titles + internal TOCs; result `type` = catalog, work or toc |
| `search/notes?q=` | collation notes, annotations, interlinear notes (extended syntax) |
| `search/variants?q=` | variant-character forms that occur, with `hits`; `scope=title` |
| `search/synonym?q=` | near synonyms (e.g. 文殊師利) |
| `search/similar?q=` | similar passages (Smith-Waterman); 6–40 characters, no punctuation; `score_min` (16), `k` (500) |
| `search/sc?q=` | simplified input → `{"q": traditional, "hits": n}` |
| `search/facet?q=` or `search/facet/<canon\|category\|dynasty\|creator\|work>?q=` | counts |
| `chinese_tools/sc2tc?q=` | simplified → traditional (plain text) |
| `word_seg2?payload=` | word segmentation |

Filters for `search`, `all_in_one`, `similar`, `variants`, `notes`, `sc`:
`canon=T` or `T,X`; `category=禪宗部類` (`a,b%2Bc,d` = (a OR b) AND (c OR d)); `work=T0026`; `works=T0026,T0099`; `creator=A000439` (same AND/OR form); `dynasty=隋,唐`; `time=800` or `time=800..900`; `work_type=textbody|non-textbody`.

`order` (search): `canon`, `category`, `juan`, `vol`, `work`, `time_from`, `time_to`, `term_hits`; add `+` or `-`; up to five fields.

### Downloads

Bulk text in many formats: https://cbdata.dila.edu.tw/stable/static_pages/download (use these instead of fetching every fascicle through the API).

## 2. DILA authority API

Endpoint: `https://authority.dila.edu.tw/webwidget/getAuthorityData.php` (GET). Body is JSON, sent as `text/html`. Add `jsoncallback=x` only for JSONP.

### Person

`?type=person&id=<A-ID or name>`

- ID → `{"data1": {...}}`.
- Name → all persons whose name or other names contain it: `{"data1": {...}, "data2": {...}, ...}`. 空海 → 7 records (空海 A000759, but also 印空海, and monks with 空海 among their other names).
- No match → `null` or `{"data1": ""}`.

Fields: `authorityID`, `name`, `class` (category in the 高僧傳), `gender`, `monk` (`y`), `zenSchool`, `zenSect`, `bornDateBegin`/`bornDateEnd`, `diedDateBegin`/`diedDateEnd` (ISO `+0774-01-01` or `unknown`), `birthDateString`, `deathDateString`, `birthPlaceCode`/`birthPlaceName`, `deathPlaceCode`/`deathPlaceName`, `dynasty` (`日本`, `唐`, `劉宋;`…), `names` (`[日文] くうかい,Kūkai,佐伯眞魚\n[中文] 教海,如空,遍照金剛`), `note` (may contain HTML links and sources), `noteFull`, `lang`.

DILA often stores the dharma name only: 虎關師鍊 is `師鍊` (A000919), 義堂周信 is `周信` (A001468). The full name is in `names`, and a search for the full name still finds it.

Human page: `https://authority.dila.edu.tw/person/?fromInner=A000759`.

### Place

`?type=place&id=<PL-ID or name>` → `authorityID`, `name`, `dynasty`, `long`, `lat`, `districtModern`, `names`, `pinyin`, `note`, `mergeTo`. Only the c. 18,000 DILA-made places are in the API; the c. 40,000 Academia Sinica places are on the website only.

### Date

- When: `?type=time&when=<code>&format=s|j|d` (`s` ISO date `+0835-04-26`, `j` Julian Day Number, `d` DILA date ID).
- Range: `?type=time&from=<code>&to=<code>&format=…`

Answer: `{"W": {"rows": "1", "data1": {...}}}` (or `F` and `T`). Live fields (2026-11-09) differ from the old documentation: `ceDate`, `JD`, `authorityID`, `dynasty`, `emperor`, `era` (reign title; old docs say `reignYear`), `yearNumber`, `yearGanzhi`, `lunar_month`, `leap_month`, `dayNumber`, `dayGanzhi`, `yearNumberCh`, `dayNumberCh`. Several rows when several regimes coexist. Chinese calendar only; for Japanese eras use `cjk-calendar`.

### Catalog

`?type=catalog&term=<word>` returns a list of 經錄 records (`authority_id` CA…, `jing_title`, `juan`, …). The matching was unreliable in testing (unrelated titles for 金剛); prefer CBETA `search/title`.

## 3. Wikidata link

Wikidata property **P1187** = "Dharma Drum Institute of Liberal Arts person ID". SPARQL:

```sparql
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P1187 "A000759" .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,ja,en". }
}
```
→ Q222227 空海. From the Wikidata item, follow P497 (CBDB ID) and other identifiers.

## 4. Quirks found in testing (2026-11-09)

- `api.cbetaonline.cn` does not resolve; use `cbdata.dila.edu.tw/stable`.
- Japanese character forms such as `師錬` fail; `search/variants` gives the CBETA form.
- `catalog_entry?q=T08` returns nothing (use `orig-T` paths or `works?canon=T&vol_start=8&vol_end=8`).
- The authority `type=person&term=` parameter is ignored (returns `{"data1": ""}`); use `id=`.
- Lay Confucian scholars (林羅山, 藤原惺窩) are not in DILA.
