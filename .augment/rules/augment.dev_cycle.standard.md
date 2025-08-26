---
type: "agent_requested"
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
      - Phase: Plan
        action: Define clear goals, constraints, and expected outputs
        notes: Request missing context explicitly; avoid assumptions

      - Phase: Postulate
        action: Propose logic structure, config schema, or algorithmic flow
        notes: Include rationale and technician-grade commentary

      - Phase: Write
        action: Generate initial code or config scaffold
        notes: Use override-friendly structure and inline audit comments

      - Phase: Implement
        action: Integrate scaffold into target environment or module
        notes: Flag integration risks and dependency mismatches

      - Phase: Test
        action: Run diagnostics, validate outputs, and capture error states
        notes: Log all test results with timestamps and session ID

      - Phase: Verify
        action: Confirm expected behavior and output integrity
        notes: Compare against goals from Plan phase; flag discrepancies

      - Phase: Fix & Repeat
        action: Repair errors, rerun tests, and iterate until no errors remain
        notes: Maintain full audit trail across cycles; mark completion explicitly

  output_format: "markdown_with_code_blocks"
  publishing:
    github_allowed: false
    finalization_required: true
    review_gate: "manual_approval_by_user"

  fallback: "Defer to user for missing context or ambiguous goals"