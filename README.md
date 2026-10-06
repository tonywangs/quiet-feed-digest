# Quiet Feed

Turn two sets of saved RSS/Atom snapshots into a finite, offline reading digest.
New and revised items appear in publisher wording, with source links and a
before/after view. Nothing is fetched, summarized, ranked for importance, or
classified for sentiment or accuracy.

This is a local command-line application. It needs Python 3.11+ on POSIX
(Linux/macOS); its runtime uses only the standard library. The verification suite
was exercised on Linux with Python 3.12. Windows is not supported because the CLI
uses POSIX signals for its processing deadline.

## Try it

From this directory, using the included **synthetic** snapshots:

```sh
python3 -m quiet_feed \
  --previous examples/previous.json --current examples/current.json \
  --start 2026-10-05T12:00:00Z --end 2026-10-06T12:00:00Z \
  --output /tmp/my-quiet-digest
```

The output directory must not exist. Open `/tmp/my-quiet-digest/index.html` in your
browser; no server is needed. It contains two newly observed items and one
revision, with one unchanged and one absent item counted as omitted. JSON retains
all five comparable records. A checked example is in
[results/example/index.html](results/example/index.html).

To install a standalone executable offline, without pip or a package registry:

```sh
python3 scripts/install.py --output "$HOME/.local/bin/quiet-feed"
"$HOME/.local/bin/quiet-feed" --version
```

The executable is a Python zipapp containing the application. It can run from
another directory with no source checkout or runtime dependencies. Installation
refuses an existing destination; use a new path for an upgrade. Put its directory
on your PATH if desired. Uninstall by removing that one executable.

## Supply snapshots

Create one previous and one current JSON manifest. Paths are relative to each
manifest, confined to that directory, and refer only to saved regular files:

```json
{
  "version": 1,
  "observed_at": "2026-10-06T12:00:00Z",
  "feeds": [
    {"id": "workshop", "label": "My workshop", "path": "workshop.xml"}
  ]
}
```

Both manifests must use exactly the same feed IDs. Keep those IDs stable across
runs; labels may change. Explicitly use an empty **valid feed** for a known empty
baseline. A missing or malformed snapshot is an error, never an empty feed.
Unknown manifest keys and duplicate JSON keys are errors.

The window describes **observation**, not publication. Require
`previous.observed_at <= start < current.observed_at <= end`, with explicit time
zones. Publication dates do not filter or sort items. This avoids dropping
undated entries or treating an old item first seen today as newly published.
There is no persistent history: comparisons depend only on the two supplied
snapshots. An item that disappeared and later returned can be newly observed
again.

Use `--max-items 25` to shorten the report (default 100, maximum 200).
Selection is new items first, then revisions, ordered by feed ID and exact
identity. This is a reproducible ordering, not an importance ranking. Source and
change filters apply to the selected cards, not the omitted records. Native
select controls, keyboard Tab navigation, visible focus, and Enter/Space
revision disclosures work offline. With JavaScript disabled, selected cards
and disclosure views remain readable; filters do not operate.

## Matching and outcomes

Identity version 1 uses the exact nonblank Atom ID or RSS GUID within a feed.
Without either, it uses the exact, validated absolute HTTP(S) article link.
It does not normalize identifiers, resolve relative URLs, remove query
parameters, or merge across publishers. Changing an identity is an absence plus
a new observation. RSS GUID `isPermaLink` does not turn a GUID into an article
link. See [semantics and coverage](docs/semantics.md) for the precise contract.

New, unchanged, revised, and absent records are retained in JSON. Revised means
that at least one supported publisher field changed; an updated timestamp alone
can count. Absence does not prove deletion. Missing identities are excluded;
conflicting duplicates exclude that identity from **both** sides. Identical
duplicates collapse with a warning.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Complete comparison; report written (warnings may exist) |
| 2 | Incomplete comparison; report written with visible warning and issue details |
| 1 | Invalid input, resource limit, write error, or collision; no successful report |
| 130 | SIGINT/SIGTERM cancellation |

Argument syntax errors also use argparse's exit code 2, without a report. Check
for the output bundle as well as the code. `report.json` contains the machine
outcome, complete comparable items, issue locations, input hashes and dates,
selection, and omission counts. A complete outcome applies to this documented
field subset, not full feed validation.

## Safety and limits

All imported text is HTML-escaped, including publisher markup. Literal tags are
visible; no imported HTML executes. The self-contained report uses a restrictive
Content Security Policy with hashes for its own style and filter script.
No images, stylesheets, fonts, articles, enclosures or other remote assets load.
Only conservatively validated HTTP(S) article links are clickable, by reader
activation. Such destinations are not vetted for trustworthiness.

DTD/entity declarations are rejected before expansion. XML depth, nodes, fields,
input bytes, entries, report bytes and elapsed processing time are capped. Inputs
are not rewritten. Outputs are exclusively created in a new directory; collisions
never overwrite files. See [limits and failure handling](docs/limits.md).

## Verify

The complete verification command, **after provisioning development browser
tools once**, is:

```sh
QUIET_FEED_BROWSER_MODULES=/tmp/quiet-feed-browser \
PLAYWRIGHT_BROWSERS_PATH=/tmp/quiet-feed-browsers \
python3 scripts/verify.py --browser
```

One-time development-only provisioning (requires network and platform browser
libraries; does not affect the runtime CLI):

```sh
npm install --cache /tmp/quiet-feed-npm-cache --prefix /tmp/quiet-feed-browser playwright@1.58.2
PLAYWRIGHT_BROWSERS_PATH=/tmp/quiet-feed-browsers \
node /tmp/quiet-feed-browser/node_modules/playwright/cli.js install chromium
```

Without browser tooling, `python3 scripts/verify.py` runs the Python tests and
isolated installed workflow and explicitly records the browser checks as
unperformed. It does not silently claim full verification. Both commands replace
normal test evidence under `results/`; `--results /tmp/verification` keeps the
checkout unchanged. No downloads occur during verification. Regenerate sample
snapshots with `python3 scripts/make_examples.py`.

[Verification evidence](results/verification.json) records actual elapsed time,
peak process RSS, artifact sizes and hashes, interpreter/parser/browser versions,
and bounded DOM counts. [Tests](tests/test_digest.py) cover 240 seeds with an
[independent oracle](tests/reference.py), hostile XML and links, limits,
collisions, serialization failures, cancellation, cleanup and determinism.
[Browser checks](scripts/browser_test.cjs) exercise filtering, keyboard controls,
revision views, focus, a 320-pixel viewport, inert hostile content and blocked
networking. These checks are not a human usability or accessibility audit.

## Scope and existing work

This is a small strict offline workflow, not a novel feed parser or a replacement
for a full reader. The design was informed by the
[RSS 2.0 specification](https://www.rssboard.org/rss-specification),
[Atom RFC 4287](https://www.rfc-editor.org/rfc/rfc4287),
[feedparser](https://feedparser.readthedocs.io/en/latest/) and
[Miniflux](https://miniflux.app/docs/index.html).
See [source review and tradeoffs](docs/related-work.md).

Real provider compatibility, human usability, assistive-technology behavior,
other browsers, and macOS execution have **not** been tested. Inputs and reported
experiments here are synthetic. Unsupported feed dialects fail explicitly;
unsupported content encodings and ambiguous links produce incomplete results.
Publisher excerpts may be partial, promotional, outdated or wrong; no article
body is fetched to check them. XHTML is reserialized as inert XML, so original
prefixes and lexical formatting are not guaranteed. This tool is not a full XML,
RSS or Atom schema validator.
