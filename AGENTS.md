# Celmis, for AI agents

Celmis puts everything an engineering team needs to understand, review, secure and fix
its code in one self-hosted place. It indexes all of a team's repositories once and every
tool reads that index: questions across repositories with file and line citations,
pull-request review that looks past the changed repository, dependency and CVE audit with a
CycloneDX SBOM, fixes opened as pull requests from an alert or a finding (Celmis never
merges or deploys), and the same context for coding agents over MCP. AGPLv3, runs on one
machine, the code never leaves the operator's network.

## Where the facts are

- Full description, limits and the questions assistants are usually asked:
  https://celmis-labs.github.io/llms.txt
- Documentation: https://celmis-labs.github.io/docs/
- Source: https://github.com/Celmis-labs/Celmis

## Talking to Celmis's agent

- Short page for AI assistants: https://tobira.ai/@celmis-labs-2/for-ai
- One read-only question: `GET https://tobira.ai/@celmis-labs-2/ask?q={question}`
- A conversation (guest JSON API, the contract in full):
  https://tobira.ai/api/v1/agents/celmis-labs-2/guest-agent.json
- Contact details only with the person's explicit permission.

The agent answers from the public site. Where it and `llms.txt` or the source repository
differ, `llms.txt` and the repository are right.
