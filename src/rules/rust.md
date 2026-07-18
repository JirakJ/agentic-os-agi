---
applyTo: "**/*.rs"
description: "Rust conventions"
---
- `cargo build`, `cargo test`, and `cargo clippy -- -D warnings` green before commit.
- `cargo-deny check advisories` for dependency vulnerabilities; deny unwrap() in library
  code paths - propagate errors with thiserror/anyhow patterns.
