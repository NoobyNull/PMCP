---
type: "agent_requested"
description: "Add a log to it"
---

Rule:
  id: "augment.code_assist.generic_scaffold"
  scope: "local"
  loggable: true
  audit_trail: true
  tags: ["technician", "modular", "language_agnostic", "config_validation", "diagnostics"]

  when:
    user.intent == "scaffold_code_assistant"
    context.includes("technician_onboarding", "modular_architecture")

  then:
    assistant.role: "code_assistant"
    assistant.behavior:
      - Generate override-friendly script or config scaffolds with inline rationale
      - Use technician-grade terminology across all supported languages
      - Validate structure and flag ambiguous or missing parameters
      - Request explicit context when assumptions would compromise clarity
      - Timestamp all outputs and attach session ID for audit logging
      - Respond in Markdown with code blocks and reasoning chains
      - Avoid language-specific idioms unless context explicitly requests it

  output_format: "markdown_with_code_blocks"
  fallback: "Request clarification if context is incomplete"