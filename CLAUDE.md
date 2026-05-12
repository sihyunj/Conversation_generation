# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository is in a pre-implementation state. As of this writing it contains only a `README.md` describing the project as "Conversation generation research." There is no source code, no build system, no tests, no dependency manifests, and no configuration files yet.

When asked to add code, ask the user about intended language, framework, and project layout before scaffolding — do not assume conventions from the project name alone.

## Branch Convention

Development for Claude-authored changes happens on the branch `claude/add-claude-documentation-Gxb5J` (per the task instructions for this workspace). The default branch is `main`. Push completed work to the designated feature branch, not `main`.

## What to Update Here Later

Once the project takes shape, this file should be updated with:
- The actual build / test / lint / run commands (single-test invocation included).
- The high-level architecture that spans multiple files (data flow, module boundaries, external services).
- Any non-obvious conventions the codebase adopts (e.g., how prompts, datasets, or model outputs are organized for the "conversation generation" research).

Do not pad this file with generic advice or speculative structure — only document what actually exists in the repo.
