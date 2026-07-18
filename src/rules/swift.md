---
applyTo: "**/*.swift"
description: "Swift conventions"
---
- Swift 6 concurrency-checked; `swift build` + `swift test --parallel` green before commit.
- SwiftLint error-severity rules must pass. Value types first; explicit access control.
- Apple Silicon is the primary target; measure before optimizing, then optimize hard
  (memory layout, allocation, vectorization where it pays).
