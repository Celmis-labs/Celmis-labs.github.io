**Celmis is self-hosted code intelligence.** It reads a set of repositories once and
keeps a symbol graph of them; asking questions, reviewing pull requests, auditing
dependencies, routing alerts and serving an MCP endpoint are then all different ways of
reading that one index, rather than five products each holding their own copy of your
code. It runs on one machine under `docker compose`, with whichever model provider you
already pay for behind it.

This is the introduction — what it does, what it refuses to do, and how to run it. The
quickest way to say why it exists is to show the thing a diff-only tool structurally
cannot do.

## One question, two repositories

I asked a question that spanned two repositories, and the answer quoted both.

The question was ordinary: *"How does the gateway talk to the payments service? Name the
function on each side."*

The answer found a Python publisher:

```python
def publish(self, batch_id: str, entries: dict[str, int]) -> None:
    """Emit one settlement event on the published topic."""
    self.producer.send(
        SETTLEMENT_TOPIC,
        json.dumps({"batch_id": batch_id, "entries": entries}).encode(),
    )
```

and a TypeScript listener in a different repository:

```ts
start(): void {
  this.bus.on(SETTLEMENT_TOPIC, (event) => {
    const payload = JSON.stringify({ type: "settlement", ...event });
    for (const s of this.sockets) s.send(payload);
  });
}
```

They never call each other. They meet on a Kafka topic. Then the answer added something
nobody asked for:

> **Duplicated contract.** The topic name (`payments.settlement.v2`) and the event payload
> structure are hardcoded in two separate repositories — `src/config.py` in payments and
> `src/contract.ts` in the gateway. Changing the topic name or the payload schema in one
> repository without updating the other will silently break the integration.

**A reviewer that reads only the diff cannot say that.** It never had the other repository
open. That is not a model-quality problem — no amount of reasoning recovers a file that
was never in the context.

## The shape of the idea

Read the repositories **once**. Build a symbol graph — deterministically, with tree-sitter,
no model involved. Then everything else is a different way of reading that one index
rather than a separate product with its own copy of your code:

- **Ask questions**, answered with `file:line` citations, across repository and language
  boundaries.
- **Review pull requests**, with knowledge of who else calls the function in the diff —
  including from a repository not in the pull request.
- **Audit dependencies**, and produce the artefacts a buyer or an auditor asks for.
- **Route what your running services are shouting about** — alerts arrive, and the index
  already knows which repository the failing service is, and who owns it.
- **Serve it over MCP**, so your own editor or agent reads the same index under the same
  access rules.

The index is the product. The rest are surfaces.

## What the review actually catches

On a real pull request in a demo repository, three findings, all on real lines:

```js
6:  const first = vals[0];              // vals is {} — undefined, not a TypeError
7:  for (let i = 0; i <= vals.length; i++)   // off by one
16: const n = parseInt(raw);            // never throws, so the catch below is dead
```

Three inline comments with `suggestion` blocks, one summary comment, **zero false
positives on that run**. I verified all three against the file in the PR branch by hand,
because a review tool that is right four times out of five is a tool you stop reading.

## The MCP server

Eighteen tools over the same index. Here is a real session, trimmed:

```
--> initialize
<-- 200   serverInfo: { "name": "celmis", "version": "1.29.1" }

--> tools/list
<-- 200   18 tools
          list_projects        get_api_surface       bootstrap_client
          search_symbols       list_accessible_repos start_integration_walk
          find_consumers       get_review            route_incident
          get_owner            get_review_policy     get_dep_audit
          get_architecture     list_deprecations     list_dep_findings
          …

--> tools/call  search_symbols
          { "project_id": "083bd97a-…", "query": "SETTLEMENT_TOPIC" }
<-- 200
          {
            "matches": [
              { "repo_slug": "…celmis-demo-gateway",  "kind": "variable",
                "file": "src/contract.ts", "line": 2 },
              { "repo_slug": "…celmis-demo-payments", "kind": "constant",
                "file": "src/config.py",   "line": 9 }
            ],
            "count": 2
          }
```

One query. Two repositories, two languages, the same contract symbol — from a client that
has never checked either of them out. `find_consumers` is the one I use most: it answers
"what breaks if I change this" across the whole set.

## Alerts, and why they belong on the same index

This is the surface I nearly left out of this article, which was a mistake, because it is
the one that closes the loop.

Your services are already producing alerts. They land in a channel where somebody has to
work out which repository the failing service actually is, who owns it, and whether the
thing that broke was touched recently. That lookup is the expensive part — not the alert.

So the same index answers it. An ingest endpoint takes the alert, a binding routes it, and
the card arrives in chat:

```
POST /webhook/alerts/{token}
  { "severity": "critical",
    "repo_hint": "celmis-codereviewer/celmis-demo-gateway",
    "title": "checkout: unhandled exception in settle()" }

→ notif_delivered event=alert_received
  repo=celmis-codereviewer/celmis-demo-gateway severity=critical
```

Review results ride the same rails — a finished pull-request review posts its own card:
`Review CHANGES · PR #4 — 0 critical · 3 error · 0 warn · 0 info`.

Two things worth stealing from how this is wired, both of which I got wrong first:

**The webhook signature is checked before anything else.** Wrong signature → `401`.
Correct → `202`. Replay the exact same delivery → `{"status": "duplicate"}` rather than a
second review and a second bill. Delivery IDs are cheap; duplicated model calls are not.

**A failed channel test must not echo the URL it tested.** Google Chat webhook URLs carry
`key` and `token` in the query string — **the URL is a credential**. `httpx` puts the
request URL in the exception text, and an early version of the endpoint returned
`str(exc)` verbatim, which meant a failed test handed the caller back the secret it was
testing. If you are building anything that tests a user-supplied webhook, go and check
that path in your own code right now.

## The surface that quietly became urgent

The dependency audit is the one part that is **deterministic end to end** — native
auditors and OSV.dev, no LLM in the loop. It produces two things.

A CycloneDX SBOM, and an evidence pack:

```
sbom/<repo>.cdx.json   CycloneDX, one per repository
findings.json          what was found against those components
timeline.jsonl         when each fact entered the record
MANIFEST.json          sha256 of every file above
```

That last file is the point. An archive of files is not evidence — nothing in it stops
the contents from having been edited afterwards. A manifest of digests means **a third
party can verify the pack without trusting the machine that produced it**:

```json
{
  "algorithm": "sha256",
  "files": {
    "findings.json": "921412d4bf97eb32fa4b3e8ad09447dab762f19d31ffec45bddb6d7962bf08e5",
    "sbom/gateway.cdx.json": "6eadeafad0043b85a51b65ddddba84ef7b43081064ed9e1b320c62838ddc3d8e",
    "timeline.jsonl": "b1815a8e3607712aa9332cd1f8d2d0ec6f93cd8dce53dd92844b8edcde790b3d"
  },
  "generated_at": "2026-08-26T19:09:41Z"
}
```

**Why now:** from **11 September 2026**, under the EU Cyber Resilience Act, manufacturers
must report an actively exploited vulnerability to ENISA and their national CSIRT within
**24 hours**. The SBOM itself is not mandated until December 2027 — which is the trap,
because on a 24-hour clock the first question is not how to word the notification. It is
whether you ship the component at all, in which service, at which version.

The document is due in 2027. The visibility it describes is needed fifteen months earlier.

### The part I am most attached to

The audit reports **what it could not check**, as prominently as what it found:

```
Not fully checked (4). Treat a zero here as unknown, not as safe.

- …demo-gateway — npm via npm-audit: no lock file
  (package-lock.json / pnpm-lock.yaml / yarn.lock) — cannot resolve the tree
- …demo-gateway — all via osv-scanner: recognised no manifest or lock file here
- …e2e-probe/requirements.txt — PyPI via pip-audit: dependency resolution failed
  — audited 4 pinned requirements directly, without the transitive tree
```

**An unchecked ecosystem reports zero vulnerabilities exactly like a clean one.** If your
tooling cannot tell you which of the two you are looking at, that gap *is* the finding.
Steal this behaviour regardless of what you use.

## Running it

One machine. Postgres and Qdrant bundled — no external cluster to provision.

```bash
git clone https://github.com/Celmis-labs/Celmis.git celmis
cd celmis
./scripts/init-env.sh          # generates .env, every secret in the format it needs
docker compose --env-file .env up -d
docker compose ps
```

On a clean server that took **197 seconds** from `git clone` to six healthy services —
measured, not estimated. About 1.1 GB of RAM at peak during indexing, 565 MB at rest.

Bring your own model key: Gemini, Anthropic, OpenAI, OpenRouter, Groq or Mistral. A free
Gemini key is enough to evaluate it. **No telemetry, no licence check** — the only
outbound calls are the ones you configure. AGPLv3, the whole thing, not open core.

## The number I am not hiding

**17th of 50** on the Martian Code Review Bench offline set, stable under all three
judges.

It measures one of the surfaces above — pull-request review on isolated
single-repository PRs. That set has no sibling service for a symbol to have consumers in,
so the cross-repository work this is built around contributes nothing to the score. It is
on the front page of the site with that explanation next to it rather than instead of it.

I also audited every one of the 79 findings the benchmark counted against us. **33 were
real defects the reference set was silent about.** That audit is published in full, with
the code for each one — partly because it is the honest thing to do, and partly because
"our precision is actually higher" is a claim nobody should accept without the evidence
attached.

## Known rough edges

- Semantic search needs a generated vault. Until you make one, the UI says so in an
  orange banner rather than quietly returning worse answers.
- The execution sandbox has deliberate internet egress, because `pip install` and
  `npm ci` need it.
- No long-term support branch. Fixes land on the latest release.
- It does not make anyone compliant with anything, and it says so in its own output.

---

The source, the docs and the full benchmark audit are in
[the repository](https://github.com/Celmis-labs/Celmis). Questions, including about the
benchmark methodology — which is the part that deserves an argument — are welcome at
[kostiantynmakoid@gmail.com](mailto:kostiantynmakoid@gmail.com).
