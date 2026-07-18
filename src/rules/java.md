---
applyTo: "**/*.java,**/*.kt"
description: "Java/Kotlin conventions"
---
- Gradle wrapper builds (`./gradlew build test`) green before commit; Error Prone and
  SpotBugs high-severity findings block.
- Explicit nullability; constructor injection; no field injection.
- JetBrains plugin projects must pass `buildPlugin` + `verifyPlugin` before release.
