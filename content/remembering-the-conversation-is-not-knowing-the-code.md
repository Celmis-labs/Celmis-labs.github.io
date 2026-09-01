A session ends. Your agent had worked out, over forty minutes, that the retry logic lives in
one service and the thing that gives up on it lives in another, that the queue name is spelled
two different ways, and that the person to ask about any of it left last year. Tomorrow you
open a new session and it knows none of that. Neither does your colleague's session. Neither
does the agent reviewing the pull request that comes out of it.

It is the same forty minutes a new engineer spends in week one, and the same forty minutes the
README would have saved if it were still true. It is why a manager asking "where is this up to"
has to interrupt someone who knows. The knowledge exists; it has nowhere to live but in people
and chat logs.

The reflex is to reach for memory. That reflex is worth interrogating, because there are two
different problems hiding under one word, and only one of them is what memory servers are for.

## What MCP actually specifies

It helps to be exact, because "MCP memory" gets said as though it were a feature of the
protocol. It is not — and the current revision makes that harder to miss rather than easier.

Read the base protocol's own three-line summary in revision `2026-07-28`: JSON-RPC message
format, **stateless, self-contained requests**, per-request capability negotiation. Servers
offer three features — Resources, Prompts and Tools. Clients offer one: Elicitation. Sampling
and Roots, which used to make that three, were deprecated in this same revision under SEP-2577,
along with Logging and Dynamic Client Registration; the migration note against Sampling reads
"integrate directly with LLM provider APIs".

There is no memory primitive and no persistence primitive. There is no memory *extension*
either — the official list is the two authorization extensions, MCP Apps, Skills over MCP, and
Tasks. Tasks is the one worth pre-empting, because it advertises "durable handles" and that
sounds adjacent: a task ID survives a disconnect so a client can resume polling a long-running
call, it carries a TTL, and what it holds is the status and eventual result of that one call.
It is durable in the sense a job ID is durable. It is not somewhere knowledge goes to live.

So every memory you have seen over MCP is a server implementing memory with ordinary tools.
Anthropic's own Memory MCP server keeps a knowledge graph in a JSONL file; other community
servers do the same job over different storage. Claude Code, separately from MCP altogether,
ships Auto Memory — a `MEMORY.md` per project, on by default since 2.1.59.

This is a compliment to those projects, not a criticism. They took a gap the protocol
deliberately left open and filled it with plain tools — exactly what the tool primitive is for.

## What they remember, and why that is the right thing for them to remember

A memory server stores what was said. Your preferences. The decision you made on Tuesday and
the reason you gave. The fact that you want British spelling and no bullet lists. Entities,
relations and observations, accumulated from conversation.

Two properties of that content matter here.

It is **personal**. My conversational memory is a bad thing to hand to you. It contains my
half-formed conclusions, my shortcuts, and things I said and then revised. Sharing it is not
an unimplemented feature; it is a category error. The value is that it is *mine*.

It is **stated**. It is true because someone asserted it. Nothing in the repository can
contradict it, because it was never derived from the repository in the first place.

For remembering a conversation, both properties are correct. Now hold them against the other
problem.

## Knowing the code has the opposite shape

"Where is this symbol used, in every repository, with file and line" is not personal. There is
exactly one right answer and everybody who has read access to those repositories is entitled
to the same one. Storing it per person means storing the same fact many times and being wrong
in a different way in each copy.

It is not stated, either. It is **derived** — a function of the current commit, and therefore
**perishable** in a way conversational memory is not. If I told you on Tuesday that I prefer
tabs, that is still true on Friday. If an agent noted on Tuesday that `apply_refund` had three
callers, that is a claim about a commit, and a merge on Wednesday can make it false without
anyone touching the note. A memory store cannot know that happened, because nothing said it.

That is the failure mode worth naming, and it is the same one that makes stale documentation
worse than none. A remembered fact about code does not decay into silence. It decays into a
confident wrong answer, indistinguishable in tone from a right one.

So: conversation is personal, stated and durable. Code knowledge is shared, derived and
perishable. Same word, opposite requirements. The fix for the second is not a better memory —
it is not memory at all. It is an index that is rebuilt from the code, that many callers read,
and that has a stated relationship to a commit.

## One implementation, which you can read

Celmis is mine, so treat what follows as a worked example rather than a recommendation. It is a self-hosted platform for most of a
development cycle — the alert that arrives, the fix that goes out, the dependency and SBOM
evidence underneath — and what this article is about is one layer of it: the index. It is
AGPL-3.0, with a carve-out for `ee/` that today holds no product code, and every claim below
names the file, so you can disagree with me by reading it.

It builds a tree-sitter symbol graph per repository and serves that same graph over MCP. Eight
languages have hand-written extractors — TypeScript, Vue, Python, Go, PHP, Java, C#, C++ — and
sixteen more (Ruby, Rust, Kotlin, Swift, Scala, Elixir, Dart, Lua, R, Solidity, OCaml, F#, Elm,
Gleam, Racket, Fortran) come from the grammar authors' own tags queries, registered at the
lowest priority so a real extractor always wins. Dockerfiles, Compose files, Helm charts and CI
workflows are matched by filename or path rather than suffix, and Kubernetes manifests by
sniffing the first few kilobytes for `apiVersion` and `kind`. Terraform is the ordinary case —
`.tf`.

The HTTP mount registers 23 tools, eighteen of which read and five of which write. A sample of
what the read half returns:

- `search_symbols` — name, kind, file, line, signature and repo slug, for definitions matching
  a name across every repository in a project.
- `find_consumers` — who calls a symbol, with repo, file and line. The list of what breaks.
- `get_api_surface` — functions whose *names* look like HTTP handlers, with a route path guessed
  from the name by turning underscores into slashes, plus method, file and line. A name-convention
  heuristic over the symbol index and nothing more; it does not read route decorators, and the
  source says so.
- `get_architecture` — the cached orientation summary for a repository, with the model that
  produced it and the timestamp, so you can see how old it is.
- `get_owner` — top git-blame authors plus matched CODEOWNERS entries for a path. This is the
  one that answers "who do I ask" without asking.
- `list_accessible_repos` and `get_my_access` — the agent asking what it is allowed to look at,
  and being told which path globs are denied.
- `start_integration_walk` — an ordered checklist of the other tool calls, returned as data, for
  a client that would otherwise fire ten guesses.

Three things about that list are load-bearing.

**It is the same index, not a copy.** The MCP tools open `settings.repo_graph_path(slug)`. So
does the retrieval layer answering a human's question in the web UI. So does the pull-request
reviewer. One graph file per repository, three readers. Celmis does hold its own clone and index
it — one copy, on your infrastructure, not one per agent or per session.

**It is the same access rules, with one exception I will name.** Every tool that returns code,
ownership or review content calls `caller_access`, which calls `resolve_access` from
`src/access` — the identical function behind the human REST endpoint and behind multi-repository
question answering. A repository you may not research is omitted and named in `blocked_repos`;
a denied path is filtered out of the matches, and `search_symbols` also reports how many it hid,
in `hidden_symbol_count`, though not every tool yet returns that count. The exception:
`list_deprecations` reads its table today without a workspace or access predicate. That is a
bug on my side, not a design, and it is being fixed. While I am being exact: the scope filter on
`tools/list` is listing hygiene, not authorisation — a scoped read client is not *shown* the
write tools, but the HTTP mount carries no per-call scope check, and a token with no scopes sees
everything. Writes are gated on the token resolving to a workspace, not on its scopes. Do not
treat a read scope as a boundary.

**It has a stated relationship to a commit.** A daily sweep runs `git ls-remote` — one network
round trip, no clone, no fetch — and compares the branch head with `last_indexed_sha`. It
reports three outcomes, not two: up to date, behind, and *could not tell*, because a check that
cannot reach the remote and renders as "no new changes" is worse than no check. Behind enqueues
an incremental pass that diffs `last_sha..HEAD`, drops the symbols for every touched file and
re-extracts them, rather than re-parsing the whole repository because one file moved.

The stdio server carries a raw-Cypher escape hatch too: it tokenises the query and rejects any
of eleven write keywords before running it — a denylist, not a parser, as its own docstring says.
It is not one of the HTTP mount's 23.

## What this does not do

Celmis's MCP server has no memory. Zero hits for memory, persist, recall or remember across
`src/mcp_server/`. It will not remember that you decided to deprecate the old endpoint, or why.
That is conversational, it is yours, and a memory server is the right tool for it — run one
alongside, and let it keep the decisions while the index keeps the code.

The honest claim is narrower than "your agent finally has long-term memory", and better. The
next engineer's agent starts out knowing what yours knew about the code, because that knowledge
was never in your chat log to begin with. It is in an index, derived from the commit, readable
by every session under the same rules, and rebuilt when the commit moves.

---

---

The pull-request reviewer placed 17th of 50 on the Martian Code Review Bench offline set —
seventeenth under all three judges, F1 between 42.7% and 47.5% depending on who is judging.
That is a deliberately unflattering number about one surface of the product and it stays. The
cross-repository capability described above contributed nothing to it: the benchmark set is
isolated single-repository pull requests and the graph came back empty on all 50, so nothing
in that table is evidence for or against this path.

Check it the way I would want it checked — register two services, put them in one project,
call `find_consumers` with a symbol you know one calls in the other, and see whether the repo,
file and line are right. The source and the docs are in
[the repository](https://github.com/Celmis-labs/Celmis); the `list_deprecations` gap named
above is the kind of thing worth mailing me about, at
[kostiantynmakoid@gmail.com](mailto:kostiantynmakoid@gmail.com).
