# Frozen compatibility audit

This is a reproducible regression audit, not a claim of general feed compatibility
or a novel feed-reading algorithm. It preserves publisher wording and the
historical snapshot comparison/identity rules. It adds three bounded corrections.

## Corpus and independent expectations

[`audit/corpus.json`](../audit/corpus.json) freezes **36 externally authored
feedparser regression fixtures** at commit
`6cdc20849a66c29e2d08b0334fceb22f210bdb26` (release 6.0.11), including upstream
paths, SHA-256 hashes, attribution and exact expected records/issues/rejections.
The fixture and unit-test license explicitly covers the tests: BSD-2-Clause,
Kurt McKee, Mark Pilgrim and contributors; see `audit/FIXTURE-LICENSE`.
All original XML bytes, including upstream test comments, are retained.
Comments are data and are never evaluated as Python.

Selection is purposive: four exact Atom identity variants; literal/escaped text,
summary/content precedence and unsupported content; alternate/enclosure links;
namespace and Unicode category cases; RSS GUIDs, description, publication date,
Dublin Core and content extensions; three base-URI patterns; and malformed XML.
The manifest is the exhaustive selection list. These minimal regression inputs
frequently omit required feed metadata and entry identities. They are **not
representative live-provider feeds** and not a random sample. Quiet Feed does
not claim full schema validation. Four selected fixtures have no entries; their
feed metadata is outside the compared subset.

Expected complete record dictionaries were hand-transcribed from fixture XML,
upstream explanations and the documented subset, before parser corrections.
They were not captured from production output. Missing dates explicitly expect
empty raw text and null UTC. Known unsupported fields expect issues, not invented
values. Malformed inputs expect strict errors. XHTML expects Quiet Feed's literal
namespace serialization rather than feedparser's stripped wrapper.

Fifteen separately labeled local probes in `audit/derived.json` extend these
patterns to nested article-link bases, invalid bases, missing identities,
summary plus hidden content, extension plus description, Unicode title and UTC
dates. `python3 audit/build_cases.py` regenerates them from literal prescriptions.
They do not increase the externally authored fixture denominator. Duplicate
identity behavior is covered by the seeded snapshot experiments and retained
historical regressions, not by a fabricated upstream fixture.

## Reader comparison and results

The independent reader is vendored feedparser **6.0.11**, with sgmllib3k **1.0.0**.
`audit/vendor/provenance.json` and `hashes.json` pin source/dependency bytes and
attribution. The latter dependency's distribution declares BSD License but has
no bundled license text; original package metadata and the underlying CPython
license are preserved. No package setup scripts execute. Optional encoding
heuristics are disabled in the adapter to avoid machine-dependent detectors.
The installed application still uses only the Python standard library.

The reader adapter imports no production code. It compares entries in order and
seven extracted fields: identity, title, link, article URL, excerpt, published,
updated. Each date field includes both raw and UTC values. Sanitization and
embedded-HTML relative rewriting are disabled; feedparser still resolves ordinary
link fields. Excerpt-kind selection is a Quiet Feed policy, tested by the manual
oracle rather than treated as a feedparser field.

| Frozen population | Upstream | Local probes |
| --- | ---: | ---: |
| Inputs | 36 | 15 |
| Manual expectation passes after correction | 36 | 15 |
| Strict rejections | 3 | 3 |
| Extracted with issues | 20 | 8 |
| Extracted without issues | 13 (4 empty) | 4 |
| Compared entry fields | 203 | 84 |
| Equal reader fields | 187 | 71 |
| Different reader fields | 16 | 13 |
| Inputs with reader differences, including rejection | 14 | 13 |

Passing an expected rejection/incomplete case is a regression success, **not**
successfully reading that feed. `results/compatibility/after.json` preserves every
actual record, issue, reader value and discrepancy. Its legacy
`reader_field_discrepancies` count includes parse-level differences: 19 upstream
and 16 local events, of which three in each population are strict rejections.
The separate entry-field counters exclude those parse events.

`before.json` was captured with unmodified catalog parser bytes. It passed 34/36
upstream expectations and 1/15 local probes; every actual before value remains
available, including permissive false-complete extraction. The original 30
catalog files were verified by Git blob hashes before edits. The local baseline
commit is `73e2a98fc6634afd72bb3c532fcd132f86e9f729`; its tree matches the supplied
catalog even though its commit identity differs from the catalog remote head.
`python3 audit/replay_baseline.py` reconstructed all 51 before-audit observations
from catalog tree `01c0ae3592ee77d8b4aa1bb62929ba2de6b33ab8`, without
changing the checkout. That optional check requires the tree object in local Git.

Remaining differences have distinct meanings:

* Feedparser uses IDs/GUIDs as missing links, sometimes even exposing a URN.
  Quiet Feed requires an explicit safe article link and keeps identities exact.
* Feedparser aliases RSS published into updated; Quiet Feed preserves separate
  published/updated fields and raw date wording.
* Feedparser decodes binary/content extensions and maps Dublin Core fields.
  Quiet Feed reports the known unsupported fields and keeps analysis incomplete.
* XHTML wrapper/prefix serialization differs; markup remains inert literal text.
* Raw relative hrefs differ from reader-resolved links by design. Only Quiet
  Feed's validated `article_url` resolves a base; no relative identity is guessed.
* The independent reader recovers malformed/ambiguous content that Quiet Feed
  rejects. Reader permissiveness is not evidence that the format requires it.

## Three corrections

1. **Atom article navigation:** inherited feed/entry/link `xml:base` now resolves
   relative article hrefs into validated HTTP(S) article URLs, including the HTML
   link. Original hrefs and identity version 1 stay unchanged. Missing/unsafe
   bases produce `unresolved_relative_link` and incomplete analysis. The upstream
   base fixtures concern feed-title markup; the article-link defect is demonstrated
   by explicitly local probes derived from that pattern and Atom's base rules.
2. **Unsupported RSS fields:** `content:encoded` is reported even beside a
   description. Dublin Core title/description/date/identifier also produce an
   incomplete-analysis issue instead of silently resembling an empty core field.
   This is an explicit unsupported result, not new extension extraction support.
3. **Summary-hidden Atom content:** content gets singleton, type, external-source,
   XHTML structure and size checks even when summary supplies the displayed text.
   Unsupported content is still not fetched or decoded. Summary precedence stays
   unchanged; malformed/ambiguous/oversized hidden content now fails explicitly.

This is intentionally not a complete Atom/RSS implementation. Unknown extensions
outside the listed fields, feed metadata, authors, categories and attachments are
still outside revision comparison. Atom MIME content, RSS content extensions,
multiple alternate links, non-ASCII IRIs, remote bases/headers, RDF/RSS 1 and Atom
0.3 remain unsupported or limited. See [semantics](semantics.md).

## Acquisition and offline replay

Everything required for the Python audit is committed, including fixtures and
reader source. No pip, network access or personal accounts are required to replay:

```sh
python3 scripts/verify_compatibility.py
```

The full verification command, also requiring Chromium, is:

```sh
env QUIET_FEED_BROWSER_MODULES=/tmp/quiet-feed-browser \
  PLAYWRIGHT_BROWSERS_PATH=/tmp/quiet-feed-browsers \
  python3 scripts/verify_compatibility.py --browser
```

Provision development browser tools once while online, if not already available:

```sh
npm install --cache /tmp/quiet-feed-npm-cache --prefix /tmp/quiet-feed-browser playwright@1.61.1
PLAYWRIGHT_BROWSERS_PATH=/tmp/quiet-feed-browsers \
  node /tmp/quiet-feed-browser/node_modules/playwright/cli.js install chromium
```

Browser mode fails if tools are absent; default mode explicitly records that
browser checks were unperformed. Reacquisition is a separate, optional online
step, never part of replay. It downloads only named revision paths and pinned
package bytes into a **new** directory and checks frozen hashes:

```sh
python3 audit/acquire.py --output /tmp/quiet-feed-reacquired
```

Reacquisition was exercised successfully: all 36 XML fixtures and 37 vendored
source/metadata/license files matched their frozen hashes. Choose another new
output path for another acquisition.

The audit compares 240 snapshot pairs (seeds 91000–91239) against records extracted
by the pinned independent reader and a quadratic comparison oracle. These include
revisions, additions, removals, identical and conflicting duplicates, missing
dates, Unicode and shuffling. They deliberately restrict extraction to agreed
safe links, stable IDs and one-line supported wording; field disagreements live
in the frozen corpus rather than being normalized away. All original 240 seeded
pairs and resource-limit, collision, unchanged-input and cleanup regressions are
also retained. There are 27 unit-test methods in the recorded run.

`audit/scenarios.py` assembles a two-source snapshot pair from six named corpus
fixtures, adding labeled local IDs, new/revised records, hostile text, a relative
article link and base. These transformations are deterministic, not represented
as upstream provider data. An installed zipapp runs with isolated Python, an empty
working directory, and socket/HTTP audit hooks. It yields three new, one revised
and one unchanged record. Replay also exercises installed incomplete/error exits,
output collision, repeated-output hashes and unchanged snapshot inputs.

Chromium exercises these reports with networking blocked: source/status filters,
before/after views, Enter/Space/Tab, hostile markup, exact article hrefs, narrow
layout, zero automatic remote requests and one deliberately blocked user article
navigation. Historical sample, hostile and 200-card browser checks also run.

`results/compatibility/verification.json` records exact versions, elapsed times,
per-installed-process peak RSS, output sizes and repeated hashes. The recorded full
run took 19.919 seconds; its corpus CLI took 0.176 seconds and 24,988 KiB peak RSS.
The corpus report sizes were 6,033 bytes JSON and 9,971 bytes HTML. These are local
fixture observations, not performance guarantees. Replays overwrite only the new
compatibility evidence; historical `results/verification.json`, example artifacts,
screenshots and all historical input examples remain unchanged. Timing/RSS values
naturally vary; report hashes must repeat.

Unperformed: representative live-provider sampling, HTTP acquisition behavior,
human usability, assistive-technology evaluation, macOS and non-Chromium browsers.
No validation of remote article availability or destination reputation is implied.

## Primary sources and existing work

The design follows established feed parsing and strict subset reporting rather
than claiming novelty. The specification and reader review used:

* [Atom RFC 4287](https://www.rfc-editor.org/rfc/rfc4287.html), sections 2, 3.1,
  4.1.3, 4.2.6 and 4.2.7: namespace/text/content semantics, exact IDs and links.
* [XML Base](https://www.w3.org/TR/xmlbase/), for inherited and overridden bases.
* [RSS 2.0](https://www.rssboard.org/rss-specification), for core item fields and
  GUID/permalink semantics; promoting a GUID into a reader link is optional.
* [feedparser relative links](https://feedparser.readthedocs.io/en/stable/resolving-relative-links.html)
  and the [pinned implementation](https://github.com/kurtmckee/feedparser/tree/6cdc20849a66c29e2d08b0334fceb22f210bdb26),
  especially namespace handlers, `api.py`, `urls.py` and regression fixtures.
  Reader recovery/mapping behavior is measured separately from specification rules.
