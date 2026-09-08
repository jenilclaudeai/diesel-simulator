# Review Lenses

## What this is, and what it is not

The project brief asked for a team: project manager, lead engineer, two senior
engineers, two PhD physics/maths engineers, two software engineers, two testers,
two non-technical end users.

These are implemented as **review lenses** — defined remits applied at decision
points — not as independent agents.

### Be clear about the limitation

Twelve personas run by one model are not twelve independent reviewers. They
share one set of blind spots. A lens catches things that a *checklist* catches:
the question you forgot to ask. It does not catch things that require genuinely
independent judgement.

**The non-technical end-user lens is the weakest of all.** A model simulating a
naive user is guessing at naivety it does not have. It will catch obvious
friction — unexplained waits, jargon, missing feedback — and it will miss
everything that makes real usability testing worth doing. This lens is a
placeholder for real users, not a replacement.

Where a lens is out of its depth, it should say so rather than produce
confident output.

---

## The lenses

### PM — Project Manager
**Remit:** sequencing, critical path, scope creep, whether a phase can actually
end.
**Blocks on:** open-ended work with no timebox or fallback; long stretches with
nothing demonstrable.

### LEAD — Lead Engineer
**Remit:** architectural coherence, seams, whether decisions compose.
**Blocks on:** a decision that contradicts an accepted ADR without superseding
it.

### SR1 / SR2 — Senior Engineers
**Remit:** failure modes, error paths, operational reality. SR1 owns the
solver/worker boundary; SR2 owns state, caching and persistence.
**Blocks on:** an unhandled failure path on a user-visible operation.

### PHY1 / PHY2 — Physics & Mathematics
**Remit:** model validity, numerical method, interpolation and integration
error, whether a simplification is defensible. PHY1 owns thermo/combustion;
PHY2 owns tribology, dynamics and numerics.
**Blocks on:** a simplification that changes the sign or order of magnitude of a
result; an interpolation applied across a strongly nonlinear variable without
justification.

### SW1 / SW2 — Software Engineers
**Remit:** implementation detail, API contracts, versioning, resource limits.
SW1 owns TypeScript/Angular; SW2 owns Python and the build.
**Blocks on:** a contract that cannot be versioned; unbounded resource use.

### QA1 / QA2 — Testers
**Remit:** acceptance criteria, testability, regression coverage. QA1 owns
functional; QA2 owns numerical and audio.
**Blocks on:** an exit criterion that cannot be objectively evaluated.

### USR1 / USR2 — Non-technical End Users
**Remit:** first-run experience, waits, jargon, whether feedback is legible
without knowing the architecture.
**Blocks on:** nothing. Advisory only — see the limitation above.

---

## Operating model

Lenses run **at decision points**, not on every response:

- before an ADR is accepted
- at a phase exit
- when a bug fix changes a physical result
- before merging anything that touches the solver

Output goes to `reviews/REVIEW-NNN.md` with findings classified:

| Class | Meaning |
|---|---|
| **BLOCK** | must be resolved before the decision stands |
| **MAJOR** | must be resolved before the phase exits |
| **MINOR** | record it, fix when convenient |
| **NOTE** | observation, no action required |

A finding that is dismissed gets a recorded reason. Silent dismissal defeats
the purpose.
