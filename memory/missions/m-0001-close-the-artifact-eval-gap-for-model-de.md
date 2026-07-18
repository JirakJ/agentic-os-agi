---
id: m-0001
title: Close the artifact-eval gap for model-dependent capabilities
status: active
priority: normal
created: 2026-07-18
updated: 2026-07-18
blocked_on: 
---

# Mission: Close the artifact-eval gap for model-dependent capabilities

## Objective
Every capability class has at least one eval, including model-dependent ones: the artifact verifier pathway in evalctl is exercised by at least one real committed eval with a reference artifact, instead of existing as untested plumbing.

## Steps
- [ ] Pick the first model-dependent capability worth measuring and define its artifact contract (what file, produced by whom, judged how)
- [ ] Write the deterministic artifact verifier and its eval spec, wired into the suite
- [ ] Produce a reference artifact, run the eval end to end, and re-baseline with it included

## Log
- 2026-07-18: created
