# CLAUDE.md

The full operating guide for this project lives in **[AGENTS.md](AGENTS.md)** — read it
completely before doing anything. It covers first-time setup (install deps → interview
the user for genres + per-session limit → have them log in → dry run → live), the golden
rules, the config reference, and how the code works.

Claude-specific note: when the user says "set this up," don't just run commands — walk
them through the two setup questions in AGENTS.md §2 (genres, count) and the login step
in §3, where the user authenticates themselves. Never enter their credentials. This tool
is print-only; Kindle giveaways are skipped automatically.
