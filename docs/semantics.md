# Input, identity and revision contract (version 1)

## Supported feed subset

* RSS 2.0 with unnamespaced `rss version="2.0"`, exactly one `channel`, and
  direct `item` children. Reads `guid`, `title`, `link`, `description`, `pubDate`.
* Atom 1.0 with namespace `http://www.w3.org/2005/Atom`, a `feed` root and direct
  `entry` children. Reads `id`, `title`, alternate `link`, `summary` (preferred)
  or `content` (fallback), `published`, `updated`.
* Atom text, HTML and XHTML text constructs are supported as **literal text**.
  XHTML requires one XHTML `div` and is XML-reserialized; prefix spelling and
  entity spelling can change. HTML is not rendered. XML entities such as
  `&amp;` decode normally; custom DTD entities are never allowed.
* Out-of-line Atom content is not loaded. Other Atom text MIME types are not
  decoded. These cases record issues and make the comparison incomplete, even
  when a summary is displayed. Content singleton, XHTML structure, and excerpt
  bounds are checked regardless of summary precedence.
* RSS `content:encoded` is explicitly reported as unsupported even when a
  description is present. Dublin Core `title`, `description`, `date`, and
  `identifier` also mark the analysis incomplete; their values are not guessed
  into core fields. A description remains the displayed excerpt.
* Multiple Atom alternate links are ambiguous here, even if they have different
  language/type attributes. They produce an issue and no selected link. The ID
  can still match the entry. No alternate link is guessed.
* Atom article links resolve relative `href` values through `xml:base` on the
  feed, entry, and link. Only `article_url` changes: original `link` and IDs stay
  verbatim. A safe absolute HTTP(S) base must come from XML, never a local
  filename. Unresolved relative Atom links mark analysis incomplete. Relative
  hrefs never become fallback identities, even when navigation can resolve them.
  RSS relative links and non-ASCII IRIs remain non-clickable. Embedded markup
  links are literal text and are not rewritten. Supply an ASCII URI (punycode
  host and percent-encoded path) if needed.
* RSS 0.9/1.x/RDF, Atom 0.3, JSON Feed, standalone Atom entries, malformed XML,
  DTDs, repeated supported singleton fields, and unexpected nested markup in
  plain fields are fatal input errors. XML encodings supported by Expat are
  accepted; the application does not perform encoding-repair heuristics.

Channel/feed metadata, authors, categories, attachments, enclosures, comments,
source elements, media elements and other extensions are outside the compared
field subset. Their changes do not count as revisions. Unknown extension fields
are ignored; no referenced URLs are fetched. Required publisher schema metadata
is not validated. A structurally valid empty feed is a complete zero-entry input.

## Identity

The conceptual key is `(stable manifest feed ID, identity kind, exact value)`.
In JSON the identity kind is prefixed as `atom:`, `rss:` or `link:`; the feed ID
is separate. Nonblank ID/GUID wins over the article link. Whitespace is preserved
in nonblank identifiers, and no case folding or Unicode normalization occurs.
Whitespace-only IDs count as missing. RSS/Atom format changes can change the
identity kind. Exact-link fallback requires a safe absolute original URL; resolving an Atom
article link does not change this identity-version-1 rule. There is no identity
URL canonicalization. No title/excerpt matching occurs.

For each snapshot, identical duplicates collapse, with occurrence warnings.
A duplicate identity with any different supported field is conflicting.
The union of conflicts from both snapshots is excluded from the comparison,
so ambiguity cannot become a false new/absent/revised classification. Missing
identities are excluded individually. Their issues carry snapshot side and
one-based entry position; conflicts carry the identity. Issues retain input
order. Raw occurrence counts remain in snapshot provenance; comparison counts
refer only to unique, nonconflicting identities.

## Payload comparison and dates

Supported payload: title, original link, validated article URL, publisher excerpt,
excerpt origin (`description`, `summary`, `content`), and published/updated dates
with raw and UTC representations. Equality is exact after XML decoding and XML
line-ending normalization. Whitespace is not collapsed. XHTML serialization is
part of the representation. A title/link/excerpt/date change is a revision;
identical supported payloads are unchanged. Metadata label/path/hash changes
alone are not article revisions. This is not a semantic diff.

RSS dates use Python's RFC-style date parser and require a timezone. Atom dates
require ISO timestamps with seconds and an explicit zone; leap seconds and
fractions beyond six digits are unsupported. Invalid dates remain verbatim with
UTC null and an issue; they make the outcome incomplete. Missing dates are
legitimate and represented as empty raw text and UTC null. Even equivalent
instants with different publisher date wording count as a raw-field revision.

New means present only in the current snapshot; absent means present only in the
previous one. Reappearing items may be new again, old publication dates can be
newly observed, and absence can reflect a rolling feed or truncation.

## Digest selection and deterministic output

Sort comparable records by status (`new`, `revised`, `absent`, `unchanged`), then
feed ID and identity using Python string ordering. Take at most `--max-items`
from the new/revised portion. All other comparable items are omitted from HTML,
with counts by status. JSON retains every comparable item, both payloads and the
selected keys. Excluded ambiguous/unidentified occurrences are issues, not
omitted comparable items. Filters operate only on the finite selection.

JSON schema and identity rule versions are currently 1. Reports contain no
wall-clock generation time, random ID, absolute input path or measured runtime.
Identical inputs/options produce byte-identical JSON and HTML. Reordering XML
entries keeps identity classifications but changes provenance hashes and can
change issue positions; it need not produce identical report bytes.
