---
applyTo: "**/*.cpp,**/*.cc,**/*.hpp,**/*.h"
description: "C++ conventions"
---
- C++23 via CMake presets; warnings are errors on changed files (clang-tidy
  --warnings-as-errors). ctest suite green before commit.
- RAII everywhere; no raw owning pointers; spans/string_view at boundaries.
- Reason explicitly about memory layout, cache behavior and vectorization in hot paths.
