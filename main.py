
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("org-mem", json_response=True, debug=True, port=5000)

# TODO: a simple memory mcp for AI
# should organize memory into a tree structure, with nodes representing concepts and edges representing relationships between them.
# layout
# ~/org/roam/
# └── agent-memory/
#   # ├── global/
#   # │   ├── preferences/
#   # │   └── knowledge/
#   # └── projects/
#       # ├── effspec-a91c3f/
#       # │   ├── project.org
#       # │   ├── architecture/
#       # │   ├── decisions/
#       # │   ├── invariants/
#       # │   ├── conventions/
#       # │   ├── problems/
#       # │   └── handoffs/
#       # └── era-engine-82be14/
#       #     └── ...
# Use a stable project ID rather than the directory name alone. A practical identity scheme is:
# <readable-slug>-<hash-of-git-remote-or-generated-uuid>
# 
# Store project-root mappings in a server-managed registry:
# ~/.local/share/org-memory-mcp/projects.json
# One Org file per memory
# 
# One-file-per-memory gives clean Git history, low sync-conflict frequency, simple archival, and useful graph nodes.
#
# ```
# :PROPERTIES:
# :ID:              0197a8d4-52dc-71ec-a1cb-0f93eb217b38
# :PROJECT_ID:      effspec-a91c3f
# :MEMORY_TYPE:     decision
# :STATUS:          active
# :CREATED:         [2026-06-25 Thu 17:30]
# :UPDATED:         [2026-06-25 Thu 17:42]
# :REVISION:        3
# :CREATED_BY:      agent
# :END:
# #+title: Preserve heap location during dereference use
# #+filetags: :agent-memory:effspec:semantics:decision:
# 
# * Context
# 
# Dereference-use keeps the heap and root pointer at the original location and tag.
# 
# * Decision
# 
# Preservation proofs must follow the existing operational semantics without
# relocating the pointer.
# 
# * Rationale
# 
# The heap operation changes accessibility information while retaining the
# runtime pointer identity.
# 
# * Related memories
# 
# - [[id:4a8fd180-cab8-4aa8-bab4-f46a71949927][Path-use preservation]]
# - [[id:d21ac314-d827-4e2b-8674-159e21984de3][Use preserves accessibility]]
# 
# * Sources
# 
# - File: =EffSpec/Pcc/Semantics.lean=
# - Theorem: =path_use_preservation=
# ```
# 
# Use id: links for every memory relationship. Org IDs are globally unique and continue to resolve when entries move between files, which makes them suitable for long-lived agent references.
# 
# MCP surface
# 
# Keep the agent-facing API compact. Six tools cover the main workflow:
# 
# memory_project   : activate a project and its memory tree
# memory_list      : list memories
# memory_search    : search for memories by type, tag, or content (semantic search)
# memory_read      : read a memory by ID or path
# memory_write     : write a new memory or update an existing one
# memory_update    : update metadata or content of an existing memory
# memory_link      : create a relationship between two memories
# memory_review    : review all memories in a project
# memory_archive   : archive a memory
#
# Memory types
# 
# Use a controlled vocabulary:
#
# overview: project purpose, components, important files
# architecture: subsystem structure and data flow
# decision: an adopted technical choice and rationale
# invariant: properties that implementations and proofs preserve
# convention: project-specific workflow or coding rules
# problem: recurring failure mode and diagnosis
# handoff: current state, dirty files, next steps
# outcome: completed work and verification evidence
#
# Store temporary plans in the agent session. Promote durable conclusions into memory. This keeps the graph useful as the number of agent runs grows.
# 
# Indexing
#
# Use SQLite
#
# Synchronization
#
# Use Git as the primary synchronization and history mechanism
#
# The server can rank memories using:
# 
# full-text relevance
# + linked proximity
# + recency
# + memory-type priority
# + pinned status
# 
# Return exact memory IDs and revision numbers so the agent can cite and update the correct nodes.

def main():
    print("Hello from org-mem!")


if __name__ == "__main__":
    main()
