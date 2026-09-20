# jevgrep

`grep`, but the pattern is a question in natural language.

![jevgrep demo](docs/demo.gif)

```console
$ cat hn-feed.jsonl | jevgrep --json "is this about a company actually shipping something?"
$ jevgrep --whole "does this module talk to the network?" src/**/*.py
$ jevgrep -c "is this an authentication failure?" /var/log/app.log
```

`grep -cE 'ERROR|WARN'` finds seven lines in the sample log. Four of them are actually
authentication failures. A regex can only match spelling; the other three are an HTTP 500, a
connection pool exhausting and a rate limit.

No embeddings, no vector index, no build step. Each record is sent to the
[Jev](https://vercel.com/ai-gateway) evaluation model as a typed yes/no question, which answers
with a **probability plus its own confidence** in about 200 ms for roughly $0.00002. That is
cheap enough to run a predicate over a whole log file, and fast enough to sit in the middle of
a pipe.

Because Jev can only answer the question it was given, it cannot wander off and invent an
explanation. A record either clears the threshold or it does not.

## Three tools, one pipe

Each one maps a Unix verb onto a different Jev question type, so they compose the way
coreutils do.

| Tool | Unix verb | Jev question | What it does |
|---|---|---|---|
| `jevgrep` | `grep` | `choice` yes/no | Keep records a predicate holds for |
| `jevsort` | `sort` | `score` | Order records by how strongly a question holds |
| `jevuniq` | `uniq` | `choice` over groups | Collapse records that mean the same thing |

```console
$ jevuniq tickets.txt | jevsort "how urgent is this for an on-call engineer?" | jevgrep -c "is this a customer-facing outage?"
```

Eight tickets in, deduplicated to five, ranked, and counted. Real run over
`examples/tickets.txt`:

```console
$ jevuniq -c examples/tickets.txt
      3 cannot log in, the password reset email never arrives
      2 checkout page returns a 500 for every EU customer, revenue is stopped
      1 the footer copyright still says 2024
      1 dark mode toggle forgets my choice after a reload
      1 add a tooltip to the export button
```

It folded three differently-worded login complaints together, and worked out that "checkout
returns a 500" and "PROD DOWN: all payments failing" are the same incident.

```console
$ jevsort --explain "how urgent is this for an on-call engineer right now?" examples/tickets.txt
[3.97 c=0.98] PROD DOWN: all payments failing, customers cannot complete orders
[3.92 c=0.93] checkout page returns a 500 for every EU customer, revenue is stopped
[2.73 c=0.59] password reset mail is not being delivered to gmail addresses
...
[0.03 c=0.97] add a tooltip to the export button
```

Note the confidence column: Jev is sure about the outage and the typo, and genuinely unsure
how urgent a password-reset failure is, because that depends on facts the ticket does not
contain.

### jevsort

```
jevsort [OPTIONS] QUESTION [FILE...]
```

Ranks highest-first. `score` questions return the expected value over the scale rather than a
bucket index, so the ordering is continuous and ties are rare.

| Flag | Meaning |
|---|---|
| `-r, --reverse` | Lowest first |
| `--top N` | Keep only the N highest |
| `--scale N` | Points on the scale, 2 to 10 (default 5) |
| `--explain` | Prefix `[score c=confidence]` |
| `--jsonl` | One JSON object per line |

Sorting needs every record before it can emit anything, so unlike `jevgrep` this one does not
stream.

### jevuniq

```
jevuniq [OPTIONS] [FILE...]
```

Shows each record the first time its meaning appears. Instead of comparing every pair, each
record is shown the groups found so far and asked which it belongs to, or whether it is new:
one request per record, not N².

| Flag | Meaning |
|---|---|
| `-c, --count` | Prefix each group's size |
| `-d, --repeated` | Only groups with more than one member |
| `-u, --unique` | Only groups with exactly one member |
| `--by ASPECT` | What sameness means here, e.g. `--by "the underlying bug"` |
| `--min-confidence F` | Never merge on an answer Jev is unsure about |
| `--max-groups N` | Groups offered as options at once (default 24) |

Two honest limitations. Grouping is **sequential** by nature, since each decision depends on
the groups that already exist, so there is nothing to parallelise and a long file takes a
while. And past `--max-groups`, only the most recently created groups compete for a match, so
a record matching a much older group starts a duplicate one instead of merging.

A low-confidence answer always starts a new group rather than merging. Merging is the
destructive direction: a wrong merge hides a record from the output entirely, while a wrong
split only costs a duplicate line you can still see.

## Install

```console
curl -fsSL https://raw.githubusercontent.com/anup-a/jevgrep/main/install.sh | sh
```

Or directly, if you already have one of these:

```console
uv tool install git+https://github.com/anup-a/jevgrep     # recommended
pipx install git+https://github.com/anup-a/jevgrep
```

From a clone, for hacking on it:

```console
uv sync
uv run jevgrep --help
```

Set credentials in the environment or in a `.env` file next to where you run it
(see `.env.example`):

```sh
JEVGREP_API_KEY=...          # or TYPESAFE_API_KEY
JEVGREP_BASE_URL=https://ai-gateway.vercel.sh/v4/ai
JEVGREP_MODEL=typesafe-ai/jev
```

## Usage

```
jevgrep [OPTIONS] PREDICATE [FILE...]
```

With no `FILE`, reads stdin. **One record per line** by default, exactly like grep.

| Flag | Meaning |
|---|---|
| `-v, --invert-match` | Select records the predicate is *false* for |
| `-c, --count` | Print only the count of matching records |
| `-l, --files-with-matches` | Print each matching origin once |
| `-n, --line-number` | Prefix output with the line number |
| `-q, --quiet` | Print nothing; signal via exit code |
| `--color WHEN` | `auto` (default, when stdout is a terminal), `always`, `never` |
| `-t, --threshold FLOAT` | Probability needed to match (default `0.5`) |
| `--min-confidence FLOAT` | Records Jev is less sure than this about never match (default `0.0`) |
| `-j, --jobs INT` | Requests in flight (default `8`) |
| `--json` | Parse each input line as JSON and send the object as the record |
| `--whole` | One record per *file* instead of per line |
| `--explain` | Prefix each result with `[p=… c=…]` |
| `--jsonl` | Emit one JSON verdict per line, for piping onward |
| `--stats` | Report record count, latency and cost on stderr |

### Exit codes

Same contract as grep, so `&&` and `if` work as you expect:

| Code | Meaning |
|---|---|
| `0` | At least one record matched |
| `1` | No record matched |
| `2` | Something went wrong (bad config, unreadable file, API failure) |

## Threshold vs. confidence

These are two different things and the distinction is the reason this tool is worth using.

- **`--threshold`** is about the *record*: how probable is it that the predicate holds?
- **`--min-confidence`** is about the *model*: how sure is Jev of its own answer?

A record can be `p=0.99, c=0.3`: "almost certainly yes, but I am guessing". Raising
`--min-confidence` pushes those into an *uncertain* bucket that never matches and is reported
on stderr, so ambiguous records get escalated to a human (or a bigger model) instead of
silently landing on one side.

```console
$ jevgrep --min-confidence 0.7 --explain "is this a security incident?" incidents.log
[p=0.98 c=0.91] 2026-09-19 root login from 203.0.113.9, no MFA
jevgrep: 3 records were too uncertain to classify (see --explain)
```

Under `--explain`, both numbers are coloured by how much they can be trusted: green at or
above 0.9, amber at or above 0.7, red below. A record the model is guessing at is obvious
at a glance. Colour follows grep's rules: on when stdout is a terminal, off when piped,
`NO_COLOR` respected, `--color=always` to force it. `--jsonl` output is never coloured.

## Recipes

```console
# Filter a JSONL feed on a field-aware predicate, keep the original lines
cat jobs.jsonl | jevgrep --json "is this role remote and paid in USD?" > remote.jsonl

# Which source files reach the network?
jevgrep --whole -l "does this module open a socket or make an HTTP request?" src/**/*.py

# Structured output for a downstream tool
jevgrep --jsonl "is this a stack trace?" app.log | jq -r 'select(.probability > 0.9) | .text'

# Use it as a test, grep-style
jevgrep -q "does this diff delete a test?" <(git diff) && echo "heads up"
```

## Behind a TLS-inspecting proxy

Two things bite here, and jevgrep handles both explicitly rather than telling you to disable
verification:

- **`httpx` pins its own certifi bundle and ignores `SSL_CERT_FILE`.** jevgrep reads
  `JEVGREP_CA_BUNDLE`, then `SSL_CERT_FILE`, and builds the TLS context itself. A bundle path
  that does not exist is an error, and verification is never silently downgraded.
- **`httpx` also inherits the macOS *system* proxy setting.** On a dev machine that is usually
  a local debugging proxy (Bifrost, Charles, mitmproxy) re-signing traffic with certificates
  OpenSSL 3 rejects outright, so requests fail for reasons unrelated to the API. jevgrep
  honours `HTTPS_PROXY` / `ALL_PROXY` (a deliberate choice) and ignores the system-wide
  toggle.

## Notes

- Blank lines are skipped without being sent (they cost money and mean nothing).
- Results stream back **in input order**, with `-j` requests in flight.
- Malformed JSON under `--json` is a hard error naming the line, not a silent skip.
- `-q` stops at the first match, so it stops spending too.
- The predicate is sent as a two-way `choice`, not a `boolean`. The gateway returns no
  confidence for boolean answers, which would quietly make `--min-confidence` a no-op.
- Provider overload arrives as **HTTP 200 with an error body**, so retries key off the message
  as well as the status. `Retry-After` is honoured on 429, capped at 30 s per record.

## Licence

MIT.
