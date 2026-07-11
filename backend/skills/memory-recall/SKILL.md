---
name: memory-recall
description: Use when a question references prior conversation, a point in time, or how a fact has changed. Activates on temporal/historical requests, not current-state lookups.
---

# Temporal / Historical Recall

Some facts in this graph are bi-temporal: a relationship can be invalidated
(superseded by a contradicting later fact) rather than deleted, so the graph
can answer both "what's true now" and "what was true as of an earlier
document." When a question is about history, change over time, or what was
previously the case, distinguish clearly between a fact's current status and
its historical status — don't collapse them into one answer.

If a fact was invalidated, say what it was, when it stopped being current
(if known), and what replaced it. If asked "as of" a specific point, only
use facts whose validity window actually covers that point — don't default
to current state when the user explicitly asked about the past.

For questions about prior conversation turns (not graph facts), rely on the
real session history already provided — never fabricate something the user
didn't actually say earlier.
