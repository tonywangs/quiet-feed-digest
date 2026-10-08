# Source review and design choices

Original design review: 2026-10-06. No novelty claim is made.

Compatibility audit update (2026-10-08): the [pinned audit](compatibility.md)
now vendors feedparser 6.0.11 solely as an independent development comparator,
with its licensed regression fixtures. It is not an application runtime
dependency. The historical review below predates that audit; its statements
about no copied code and no fixture comparison describe the original milestone.

* [RSS Advisory Board, RSS 2.0 specification](https://www.rssboard.org/rss-specification):
  GUIDs identify items, and descriptions can contain entity-encoded HTML. This
  tool retains GUID strings for matching and exposes description markup as text.
  It supports the documented RSS 2.0 item subset, rather than every extension.
* [RFC 4287, Atom Syndication Format](https://www.rfc-editor.org/rfc/rfc4287):
  Atom separates stable entry IDs from links and distinguishes text constructs
  and timestamps. This implementation uses feed-scoped IDs and exposes raw dates
  alongside UTC forms. Conservative handling of multiple alternate links and
  unsupported text types is an application restriction, not an Atom requirement.
* [feedparser documentation](https://feedparser.readthedocs.io/en/latest/) and
  [its parser mixin implementation](https://github.com/kurtmckee/feedparser/blob/develop/feedparser/mixin.py):
  feedparser has extensive namespace handling, relative URI resolution and HTML
  sanitization machinery. Quiet Feed intentionally accepts a smaller strict
  input subset, rejects malformed XML, and avoids rendered publisher HTML. It
  does not claim feedparser's compatibility breadth. No feedparser code is copied
  and it is not a dependency.
* [Miniflux documentation](https://miniflux.app/docs/index.html) and
  [reader processing implementation](https://github.com/miniflux/v2/blob/main/internal/reader/processor/processor.go):
  Miniflux is a full feed-reader system with an entry-processing pipeline. This
  project focuses on an explicit two-snapshot local comparison with no fetching,
  account, database or background process. Snapshot provenance and finite reports
  are workflow choices, not new syndication concepts. No Miniflux code is copied.

Source URLs for implementations follow moving branches. The compatibility
statements above describe the reviewed design, not a benchmark or a claim about
all present/future versions of those projects. Provider fixtures, broad parser
comparisons and live feeds have not been evaluated. The synthetic fixtures make
identity and failure behavior reproducible without redistributing news articles.
