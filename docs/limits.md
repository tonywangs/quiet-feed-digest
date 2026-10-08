# Resource bounds and failure behavior

Hard bounds apply before publication. They are not silently increased.

| Resource | Limit |
| --- | ---: |
| Feeds per manifest | 20 |
| Each manifest | 65,536 bytes |
| Each feed snapshot | 1,048,576 bytes |
| Sum of all previous/current snapshot reads | 16 MiB |
| Entries per feed snapshot | 2,000 |
| Total previous/current entry occurrences | 10,000 |
| Excerpt per entry | 8,192 Unicode characters |
| Other supported scalar field | 2,048 Unicode characters |
| Each manifest string | 256 characters; feed ID at most 64 |
| XML nesting depth | 32 elements |
| XML elements per snapshot | 50,000 |
| Selected HTML cards | 200 (100 default) |
| Each final JSON/HTML artifact | 8 MiB |
| CLI parse/compare/serialize/write time | 30 elapsed seconds (lower with `--timeout`) |

Size, format, manifest, time and I/O failures terminate with an error, rather than
publishing an empty-success digest. All feeds must parse; there is no partial
feed skipping. Identity/content/date problems instead yield an explicitly
**incomplete** report with issue details. Non-clickable links and identical
duplicates are warnings alone; if an unsafe link also leaves no identity, that
missing-identity issue makes the result incomplete. Unresolved relative Atom
links now have an additional incomplete-analysis issue. Atom content is subject
to the excerpt limit even when a summary is displayed; base attributes and
composed bases are bounded by the scalar-field limit.

Output serialization and byte-size checks finish before creating the output
directory. `mkdir` reserves that directory exclusively; existing files,
directories and symlinks are collisions. Each file is created exclusively and
fsynced. The `INCOMPLETE` marker is removed only after both files finish.
Catchable exceptions, SIGINT and SIGTERM during writing clean up the owned
directory. SIGKILL, process crashes, power loss, directory tampering or filesystem
failures can leave a partial directory; never consume a bundle with an
`INCOMPLETE` marker. No crash-atomic two-file publication or power-loss durability
is claimed. After inspecting a stale bundle, remove it or choose a new output
path. Inputs are never opened for writing.

Only regular input files are accepted. Nonblocking opens avoid hanging on FIFOs.
Manifest paths cannot be absolute, include `..`, or resolve outside the manifest
directory. Local directory contents and the output parent should be trusted and
stable during the run; this is not a sandbox against a concurrent attacker who
can replace filesystem paths. Network filesystems can have uninterruptible kernel
I/O, so the userspace elapsed-time alarm is not a hard operating-system execution
quota. Library calls do not install the CLI alarm.

The parser rejects DOCTYPE and entity declarations via Expat callbacks, including
UTF-16 documents. It never fetches an external entity. Namespaces are expanded
before field matching. Markup, URLs and all source labels are escaped in the
report; a hash-based CSP permits only the application's fixed script and style.
The URL policy accepts ASCII absolute HTTP(S), no credentials, whitespace,
backslashes, control characters, malformed escapes or invalid ports/host syntax.
It does not validate destination reputation or prohibit private-network article
links. Reader activation leaves the local report and may make a network request.
No request occurs just by viewing/filtering the digest.

Measurement values are observations for the included fixtures, **not** performance
promises for every allowed input. Peak RSS is per installed CLI process on Linux;
verification-suite/browser RSS is not included in that measure.
