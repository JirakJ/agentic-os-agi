---
description: Human-approved 10-minute override for a protected gate action (logged)
---
The user is explicitly authorizing a one-off gate override (10-minute TTL).
1. Confirm with the user what they are overriding and why (one sentence).
2. Run: `mkdir -p ~/.jj-agentic-os && touch ~/.jj-agentic-os/gate-unlock`
3. Tell them the override window is 10 minutes, every use is logged as `gate_override`
   telemetry, and permanent gate changes still require an ADR in adr/.
Never create this marker without the user's explicit instruction in this conversation.
