# Internal AI Agent Tooling

This directory is reserved for adult/internal automation only.

Allowed examples:

- expedition drafting for human review
- content linting and schema repair suggestions
- species blurb drafts from grounded source material
- docs drift checks
- CI/deploy triage summaries
- closed-beta feedback summaries
- moderation-review summaries for adults

Forbidden:

- importing agent frameworks from `backend/app`
- controlling API routing, auth, observation writes, moderation decisions, or rewards
- live kid-facing LLM calls
- sending kid-uploaded photos or kid free text into an agent workflow without a new ADR

Any CrewAI or multi-agent framework adoption must first land an ADR and a
small proof of concept that proves outputs are reviewable, cached, validated,
and kept outside the production request path.
