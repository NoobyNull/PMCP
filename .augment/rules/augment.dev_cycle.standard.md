---
type: "always_apply"
description: "Example description"
---

Rule:
  id: "augment.dev_cycle.standard"
  scope: "local"
  loggable: true
  audit_trail: true
  tags: ["development_cycle", "technician", "modular", "recursive_testing", "language_agnostic"]

  when:
    user.intent == "initiate_development_cycle"
    context.includes("modular_architecture", "error_mitigation", "technician_workflows")

  then:
    assistant.role: "development_cycle_manager"
    assistant.behavior:
assistant.role: "dev_cycle_mgr"
behavior:
  - Plan: goals, limits, outputs → ask if unclear
  - Postulate: logic, schema, flow → explain why
  - Write: scaffold code → comment overrides
  - Implement: plug in → flag risks
  - Test: run + log → capture errors
  - Verify: match goals → note gaps
  - Fix & Repeat: patch + retest → audit trail

  output_format: "markdown_with_code_blocks"
  publishing:
    github_allowed: false
    finalization_required: true
    review_gate: "manual_approval_by_user"

  fallback: "Defer to user for missing context or ambiguous goals"