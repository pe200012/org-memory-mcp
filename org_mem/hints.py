"""Static MCP resource hints for agents using org-mem.

This module owns concise, server-published guidance text. The FastMCP server
registers these strings as read-only resources.
"""

from __future__ import annotations

GUIDE_URI = "org-mem://guide"
SCHEMA_URI = "org-mem://schema"
WORKFLOW_URI = "org-mem://workflow"

GUIDE_TEXT = """# org-mem Agent Guide

Use org-mem for durable project memory backed by readable Org files.

Core pattern:
1. Start repo work with memory_project(root_path, name_hint=None).
2. Search before design, review, debugging, and implementation with memory_search.
3. Write durable facts with memory_write.
4. Update existing facts with memory_update(memory_id, expected_revision, ...).
5. Link related records with memory_link.
6. Archive superseded records with memory_archive.
7. Refresh the project overview with memory_review after meaningful changes.

Search first for decisions, conventions, problems, handoffs, architecture notes, and outcomes. Prefer updating an existing memory when the new fact changes the same durable record. Prefer writing a new memory when the fact has a distinct lifecycle or evidence trail.
"""

SCHEMA_TEXT = """# org-mem Schema Guide

Memory types:
- overview
- architecture
- decision
- invariant
- convention
- problem
- handoff
- outcome

Required Org sections:
- Content
- Sources
- Related memories

Type-specific sections:
- decision: Context, Decision, Rationale, Consequences
- problem: Symptoms, Diagnosis, Fix, Prevention
- handoff: Current state, Verification, Next steps
- outcome: Change, Evidence, Follow-up

Agent-written non-overview memories require evidence. Good evidence names concrete file paths, symbols, commands, test results, issue links, external URLs, or user decisions.

Updates use optimistic concurrency. Read the current memory, keep its revision, and call memory_update(memory_id, expected_revision, ...). Stale expected_revision values produce a revision_conflict response.
"""

WORKFLOW_TEXT = """# org-mem Workflow Guide

Start:
1. Call memory_project(root_path=<repo root>).
2. Search with memory_search(project_id, query, memory_type=None, status="active").
3. Read relevant records with memory_read(memory_id).

During work:
1. Use memory_write for new durable decisions, conventions, problems, handoffs, and outcomes.
2. Use memory_update with expected_revision for records that already exist.
3. Use memory_link to connect related decisions, fixes, and outcomes.
4. Use memory_archive for superseded or obsolete records.

Review:
1. Gather memory IDs and revisions considered during the review.
2. Synthesize the project overview text.
3. Call memory_review(project_id, overview_body, reviewed_revisions, expected_revision=None or current revision).

The reviewed_revisions argument records the source memory IDs and revisions behind the overview update.
"""

RESOURCE_TEXTS = {
    GUIDE_URI: GUIDE_TEXT,
    SCHEMA_URI: SCHEMA_TEXT,
    WORKFLOW_URI: WORKFLOW_TEXT,
}


def resource_text(uri: str) -> str:
    """Return static hint text for a known resource URI."""
    return RESOURCE_TEXTS[uri]
