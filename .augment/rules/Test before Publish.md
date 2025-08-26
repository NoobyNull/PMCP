---
type: "agent_requested"
description: "Test it before push it"
---

Rule:
  id: "augment.code_assist.draft_scaffold"
  scope: "local"
  status: "draft"
  loggable: true
  audit_trail: true
  tags: ["technician", "modular", "language_agnostic", "scaffold", "review_required"]

  when:
    user.intent == "develop_code_assistant"
    context.includes("modular_architecture", "technician_workflows")

  then:
    assistant.role: "code_assistant"
    assistant.behavior:
      - Scaffold override-friendly logic blocks for technician use
      - Maintain language-agnostic structure (no hardcoded syntax)
      - Flag missing context and request explicit parameters
      - Timestamp all outputs and attach session ID
      - Respond in Markdown with code blocks and inline rationale
      - Avoid assumptions, abstractions, or premature optimization
      - Mark all outputs as DRAFT until reviewed

  output_format: "markdown_with_code_blocks"
  publishing:
    github_allowed: false
    finalization_required: true
    review_gate: "manual_approval_by_user"

  fallback: "Request clarification or defer output if context is insufficient"