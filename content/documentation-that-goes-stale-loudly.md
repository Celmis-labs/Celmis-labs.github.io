There is a diagram your organisation has never drawn. On it, one box holds most of what is
known about how the system works: which service owns the settlement flow, why the retry lives
on the consumer and not the producer. The box is a person. They are competent, generous with
their time, and currently in Croatia.

Everyone knows this. What gets missed is that the wiki does not fix it. The wiki was written
during a documentation push eighteen months ago and has been quietly wrong since the week
after. The README describes a deployment that no longer exists. The architecture page still
shows the monolith that was split in March.

An absent document and a false one are not the same failure. An absent one sends you to the
code, which is annoying and correct. A false one sends you somewhere confidently, and you find
out forty minutes later, having built a mental model on top of it. The wiki nobody trusts is not
neutral. It is a trap already sprung on several new joiners, and the response is always the
same: ask the person.

So the person is the interface, and the wiki is a decoy pointing at them.

## Two ways to go stale

Take any statement about a codebase — "requests are authenticated in the gateway". At some
moment it stops being true. What happens then is the entire distinction.

**Hand-written documentation goes stale silently.** There is no event. Somebody merges a pull
request, and a page in Confluence becomes false. Nothing fires, no build turns red, the
timestamp does not move. Its confidence is unchanged, which is the problem: the page is now
more sure of itself than the code justifies. A stranger discovers it months later, at the worst
possible time, and between falsity and discovery the document costs more than not having it.

**Documentation derived from the code goes stale loudly**, because the generator runs again.
The commit that made a statement false is the input to the next run. Staleness stops being an
unobserved property of a page and becomes an event with a timestamp: a job, a diff, a
regenerated file, a failure. You can put that on a dashboard. You cannot page on Confluence
being wrong, because nothing knows.

That is the whole argument, and it is smaller than it sounds. Not that machines write better
prose — they very often do not. It is a claim about *observability of decay*, and decay is what
kills documentation, not prose quality.

## Where the loud kind fails, before I sell you on it

Four honest limits, because the sales version of this argument skips all of them.

**A generator recovers *what*, never *why*.** It can tell you this module publishes to that
topic. It cannot tell you the retry sits on the consumer because of an incident in 2023 and a
vendor who would not fix their idempotency. That was never in the code and no parsing recovers
it; it lives in the person in Croatia. Generated documentation shrinks the set of questions that
need a person; it does not empty it.

**Regeneration is not free.** Every regenerated page is model spend. A system that rewrites
everything on every commit gets switched off, and a generator that is switched off is a
hand-written wiki with extra steps.

**Silent success is the real bug.** A run that produces nothing looks identical from outside to
a run that worked: job completed, no errors, folder empty. If a pipeline fails quietly, the
loudness you paid for is gone.

**Derived documentation must name what it does not cover.** A generated set that silently skips
six of nine services is the same trap as the stale wiki, in a fresher timestamp.

Build this yourself and those four are the specification. Below is one worked answer.

## One worked answer

This part is about Celmis, which is mine — a self-hosted
platform for the middle of a development cycle, AGPL-3.0-or-later, under docker compose. It
keeps an index of the code current, and several things come out of that index: alerts you can
act on, a dependency and vulnerability picture, questions answered across repository
boundaries. Documentation is the one this piece is about. Every claim below is in the tree,
including the two places where it does less than you would assume.

**Noticing.** A scheduled sweep, once a day by default, does one `git ls-remote` per registered
repository: one round trip, no clone, no fetch. It records four outcomes, not two — up to date,
behind, never indexed, and *could not tell*. The fourth matters most: a check that cannot reach
the remote and renders as "no new changes" answers wrongly while wearing a fresh timestamp. The
sweep is the floor under the push webhook: a webhook only fires where somebody registered one.

**Narrowing.** When the branch has moved, the re-index is incremental: it walks
`git diff last_sha..HEAD` and touches only what changed. A reverse index — built by reading
which source files each generated note names in its frontmatter — resolves those changed files
back to the documents that name them. Their vectors are dropped from the search index at once,
so search stops returning removed content before any rewrite starts. Module notes are then
rewritten against the current code; everything else is re-embedded from disk, which restores
search without paying a model for prose that may not have moved.

And the limit I would rather write than have you find. Feature and integration notes record
their symbols as `file::name` graph ids, so a changed file resolves to them. A module note
records a *directory* plus bare symbol names, and the lookup is an exact match on the changed
file's full path — so editing `src/auth/login.py` does not currently select `modules/auth.md`.
The note type that gets the real rewrite is the one the index is worst at selecting. Thirty
lines in `src/vault/reverse_index.py`, and exactly the class of bug a hand-written wiki has no
way to even have.

**Not paying twice.** Each note carries the commit it was written from, and for module notes —
the bulk of a vault — a matching commit is skipped outright next run. Better: when the commit
differs but none of that module's files changed between the two, the stamp is advanced and no
model is called. If git cannot answer — a shallow clone, a missing revision — the code
regenerates rather than skips. Feature and integration notes carry the same stamp but are not
yet gated on it: generate twice at one commit and you pay for those twice.

**Refusing.** Ask it to document a repository that was never indexed and it refuses that
repository by name and says why, rather than writing pages from filenames. Ask for everything,
and a `missing_only` condition means what people actually want — the services that have none —
not a rewrite of all of them.

**Failing loudly.** A run in which every document failed used to report success, because the
markdown folder existed. It now raises. So does a subtler one: three production jobs reported
`completed`, `attempts: 1`, `last_error: null` and wrote zero vectors — the documents existed,
only the embedding half had failed. The job is not done unless both halves land.

**Saying what produced it.** Every note a model wrote carries a provenance block: generator and
version, commit, engine, model, timestamp, and — the useful one — the number of index lookups
the writer made. There are two engines. One packs code and metadata into a single prompt.
The other is an agent holding the platform's own MCP tools and nothing else — no shell, no file
reads, no grep — so it cannot open a file and can only ask the index: what calls this, what is
the public surface, what is deprecated. A document written after twelve lookups deserves
different weight from one written from a single prompt: on an agent-written document that count
is in the frontmatter, not a log, and a single-prompt document names its engine and carries no
count. The three assembled pages — index, architecture overview, security findings — come from
the graph and the scanner rather than a model, and carry no block yet. An awkward gap: the
architecture page is the one most likely to be exported and forwarded.

The block survives export, and the model name is rewritten on the way out to drop this
installation's own workspace identifier, which would otherwise ride into an emailed Word file
and tell a stranger nothing but an internal id. That redaction is on the export path, not the
stored note: open the frontmatter on disk and the full deployment name is still there.

**Naming the gaps.** Exporting every repository's documentation as one archive writes a
`MISSING.txt` listing the repositories that have none. A download that silently covers six of
nine services is the failure this is meant to avoid, and counting folders is not how anyone
finds out.

Underneath is a tree-sitter symbol graph — hand-written extractors for the major languages,
generic tag-query extractors for a long tail, and Dockerfiles, compose files, Kubernetes
manifests, Helm charts, Terraform and CI workflows in the same graph, not a separate one.
Repositories can be grouped, and deployment references that cross a repository boundary — a
compose or Kubernetes image, a build context — are resolved to the repository that provides them
and stored as edges in the group's graph; cross-repository calls and imports are not
materialised that way yet. When the platform answers in prose, the citations it renders as links
are re-checked against the files on disk: the file must exist, the cited line must be inside it,
and any quoted code must actually appear there — that last check exists because a model once
invented a plausible function and hung it under a real path. Failures are reported beside the
answer, not dropped.

## What it still does not do

It does not know why. It does not replace the person in Croatia; it shortens the queue outside
their inbox and moves the questions in it from "how does this work" towards "why did we decide
this". It cannot document a repository it has not indexed, and says so rather than guessing. It
costs model spend, bounded but not zero. And two of its own mechanisms are narrower than you
would assume — which is why they are named above rather than left for you to trip over.

None of that is fixed by better prose. It is fixed by documentation being an artefact with a
build, a provenance record, and a failure mode that shows up on a dashboard instead of in the
face of a new joiner nine months from now.

The wiki cannot fail. That is what is wrong with it.

---

The source and the docs are in [the repository](https://github.com/Celmis-labs/Celmis).
The two narrow mechanisms named above are the ones I would push on first if I were reading
this sceptically; if you do, [kostiantynmakoid@gmail.com](mailto:kostiantynmakoid@gmail.com).
