<!--
  Sync Impact Report
  ==================
  Version change: 1.0.0 → 1.1.0
  Bump rationale: MINOR — expanded Governance section with amendment
    procedure, versioning policy, and compliance review; tightened
    principle language to MUST/SHOULD.

  Modified principles:
    - I. Model-Agnostic Design — language tightened (MUST)
    - II. Musical Fidelity — language tightened (MUST)
    - III. Never Destructive — language tightened (MUST/MUST NOT)
    - IV. Professional Quality Output — language tightened (MUST)
    - V. Graceful Degradation — language tightened (MUST)

  Added sections: none
  Removed sections: none

  Templates requiring updates:
    ✅ .specify/templates/plan-template.md — Constitution Check is
       dynamic; no update needed.
    ✅ .specify/templates/spec-template.md — no constitution-specific
       references; no update needed.
    ✅ .specify/templates/tasks-template.md — no constitution-specific
       references; no update needed.
    ✅ .specify/templates/checklist-template.md — no constitution-specific
       references; no update needed.
    ✅ README.md — no constitution references; no update needed.

  Follow-up TODOs: none
-->

# xLights MCP Server Constitution

## Core Principles

### I. Model-Agnostic Design

All features MUST work with any xLights show configuration.
Contributors MUST NOT hardcode model names, group patterns, or
controller-specific logic. The server MUST detect capabilities
from the show XML (`display_as`, `face_definitions`, model groups)
and adapt automatically.

- Every effect mapping MUST key off model type, not model name.
- Controller references MUST come from the user's
  `xlights_networks.xml`, never from defaults in source code.
- New features MUST be validated against a show with zero
  pre-existing sequences to confirm no implicit dependencies.

### II. Musical Fidelity

Every effect placement MUST be justified by audio analysis
data — beats, onsets, stem energy, section structure, or
frequency bands. Arbitrary timing is prohibited. Sequences
MUST look intentionally choreographed to the music when viewed
in xLights.

- Effect start/end times MUST align to detected musical events.
- Section-level choices (palette, intensity) MUST reflect the
  song structure (verse vs. chorus vs. bridge).
- If audio analysis yields no usable data for a segment, the
  server MUST fall back to uniform beat spacing rather than
  random placement.

### III. Never Destructive

The server MUST NOT overwrite existing `.xsq` files. Generated
sequences MUST receive incremented suffixes (e.g.,
`(generated 1)`, `(generated 2)`). Stem separation results and
audio analysis MUST be cached. User show configurations
(`xlights_rgbeffects.xml`, `xlights_networks.xml`) are
read-only — the server MUST NOT modify them.

- File writes MUST be limited to the show folder (sequences)
  and `~/.xlights-mcp/` (config and cache).
- Deletion of user files is unconditionally prohibited.

### IV. Professional Quality Output

Generated sequences MUST match the quality expectations of the
xLights community. Effects MUST use correct xLights parameter
names and valid value ranges. XML output MUST open cleanly in
xLights without errors or warnings.

- Every generated `.xsq` MUST be parseable by xLights 2024+.
- Color palettes MUST use valid hex or named xLights colors.
- Effect parameters MUST stay within documented xLights ranges.

### V. Graceful Degradation

Optional dependencies (Demucs, Whisper, madmom) enhance quality
but MUST NOT block core functionality. If stem separation fails,
the server MUST use full-mix analysis. If lyrics detection fails,
singing faces MUST be skipped. The server MUST always produce a
usable sequence from any valid `.mp3` input.

- Core analysis (librosa) has no optional gates.
- Every optional-dependency code path MUST have a try/except
  that falls back to a simpler alternative.
- MCP tools MUST return dicts with clear error messages, never
  raise unhandled exceptions.

### VI. Testing/Test-Driven Development (NON-NEGOTIABLE)

- All new functionality MUST follow the Red-Green-Refactor
  cycle: write a failing test, implement the minimum code to
  pass, then refactor.
- Tests MUST be written and confirmed to fail before any
  production code is written for that behaviour.
- Every user story MUST have at least one acceptance-level test
  that can be executed independently.
- Acceptance tests must be written in an adversarial manner
  testing edge cases and boundary conditions as if the tester
  is an user tha has no knowledge of the application. The tests
  must try to break the app.
- Refactoring MUST NOT change externally observable behaviour;
  the existing test suite MUST continue to pass.
- **Code Coverage**: Unit tests and acceptance tests MUST
  achieve 100% code coverage. No production code may exist
  without a corresponding test that exercises it. Coverage
  MUST be measured and enforced in the CI gate.
- **Arrange-Act-Assert (AAA)**: All tests MUST follow the
  Arrange-Act-Assert pattern. Each test method MUST contain
  exactly three clearly separated sections marked with
  `// Arrange`, `// Act`, and `// Assert` comments. The
  Arrange section sets up preconditions and inputs. The Act
  section invokes the behaviour under test. The Assert section
  verifies the expected outcome. Sections MAY be omitted only
  when they would be genuinely empty (e.g., no arrangement
  needed for a static method with no dependencies), but the
  remaining sections MUST still be commented.
- **Bug Fix Regression Tests (NON-NEGOTIABLE)**: Every bug fix
  MUST start with the creation of one or more failing tests
  (unit and integration). This builds our regression suite.
- **5-Minute Debug Limit (NON-NEGOTIABLE)**: When debugging an
  issue (failing test, broken deploy, unexplained behaviour),
  the agent MUST stop after 5 minutesof unsuccessful
  investigation and brief the user with: (a) what was checked,
  (b) what is known vs. unknown, and (c) the candidate hypotheses.
  No "one more search", no "let me just check", no follow-up
  rabbit holes. Brief and wait for guidance.

**Rationale**: TDD produces verifiable, regression-resistant
code and ensures every feature is exercised by automated tests.
Mandating 100% coverage eliminates untested paths and prevents
silent regressions.

## Technical Constraints

- Python 3.11+ with type annotations throughout.
- Pydantic models for all data structures crossing module
  boundaries.
- MCP protocol via FastMCP — tools MUST return dicts, not raise
  exceptions.
- Audio analysis via librosa (core), Demucs (stems),
  Whisper (lyrics).
- xLights XML format MUST match the output of xLights 2024+
  exactly.

## Quality Standards

- **Effect variety**: no model MUST have the same effect for
  more than 2 consecutive sections.
- **Palette variety**: colors MUST change at least every
  2 sections.
- **Layer separation**: bed (L0), motion (L1), and accent (L2)
  MUST serve distinct visual purposes.
- **Singing models**: singing models get dedicated layers —
  regular effects MUST NOT be mixed with Faces on the same
  layer.

## Governance

This constitution governs all spec-driven development on this
project. Feature specs MUST demonstrate compliance with these
principles before implementation begins.

### Amendment Procedure

1. Propose changes via a pull request modifying this file.
2. The PR description MUST state which principles are affected
   and the rationale for the change.
3. At least one maintainer MUST approve the amendment.
4. After merge, update the version and `Last Amended` date
   below.

### Versioning Policy

This constitution follows semantic versioning:

- **MAJOR**: Removal or incompatible redefinition of a
  principle.
- **MINOR**: New principle or materially expanded guidance.
- **PATCH**: Clarifications, wording, or typo fixes.

### Compliance Review

- Every feature spec MUST include a Constitution Check section
  referencing the principles it touches.
- Code reviewers SHOULD verify that new MCP tools satisfy
  Principles I, III, and V before approving.

**Version**: 1.1.0 | **Ratified**: 2026-04-05 | **Last Amended**: 2026-04-06
