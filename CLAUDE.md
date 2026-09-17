# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`agent-lab`: a repo for experimenting with LLM agent designs by combining tools, agents, and workflows. Built on LangChain `create_agent`, talking to any OpenAI-compatible endpoint (default: local Ollama, `qwen3.5:9b`).

Three layers, plus a record of results:
- **Tool** — a `@tool` function in `tools/`. The smallest part.
- **Agent** — a system prompt plus a tool list, in `agents/`. Currently eight: `agent` (general assistant), `researcher`, `coder`, and `planner`, `optimizer`, `reviewer`, `evaluator`, `debugger`.
- **Workflow** — how agents are chained. Currently documented in README "워크플로" and chained by a human; there is no workflow code yet (see "Adding things").
- **Experiment record** — README "실험 기록": which combination produced which result.

Everything user-facing — system prompts, tool docstrings, tool return strings, comments, README, commit messages — is written in Korean; keep it that way.

## Commands

```bash
uv sync                                   # install (Python 3.13, uv)
uv run agent "질문"                        # one-shot: answer and exit
uv run coder                              # no args: interactive REPL (Ctrl-D to quit)
WORKSPACE_ROOT=~/proj uv run coder "..."  # file/shell/bench tools operate under WORKSPACE_ROOT
```

Entry points are `[project.scripts]` in `pyproject.toml` → functions in `cli.py`. There is no test suite, linter, or formatter configured. Verify changes by running the relevant agent against a real endpoint.

Config comes from env vars or `.env` (env vars win): `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_API_KEY`, `DOCS_ROOT`, `WORKSPACE_ROOT`, `BENCH_PYTHON`. See `.env.example`.

## Architecture

- `llm.py` — `build_llm()` returns a `ChatOpenAI` with `temperature=0`. Env is read at import time.
- `agents/base.py` — `build(system_prompt, tools)` wraps `create_agent` with an `InMemorySaver` checkpointer (conversation memory lives only within the process). `ask(agent, question, thread_id)` invokes the agent, strips everything before the last `</think>`, and if the final content is empty, falls back to listing the `ToolMessage`s from the current turn (`_current_turn` slices after the last `HumanMessage`, since the checkpointer returns prior turns too).
- `agents/<name>.py` — each is just a `SYSTEM_PROMPT` plus a `build_<name>()` factory calling `build(SYSTEM_PROMPT, <TOOL_LIST>)`. Re-exported from `agents/__init__.py`.
- `tools/__init__.py` — calls `load_dotenv()` **before** importing tool modules, because modules like `tools/workspace.py` and `tools/bench.py` read env vars at import time. Defines the per-agent lists: `TOOLS`, `RESEARCH_TOOLS`, `CODING_TOOLS`, `OPTIMIZE_TOOLS` (= `CODING_TOOLS`), `EVALUATE_TOOLS`, and `PLAN_TOOLS`/`REVIEW_TOOLS`/`DEBUG_TOOLS` (all = read-only `READ_TOOLS`).
- `tools/workspace.py` — `ROOT` from `WORKSPACE_ROOT`; `resolve()` returns `None` for paths escaping the root, and every file tool in `code.py`/`bench.py` must check that. `run_command` (`tools/shell.py`) is a raw shell with `cwd=ROOT` and is **not** sandboxed.
- `tools/bench.py` — `benchmark`, `compare_outputs`, `compile_check` generate a Python script (a `_PRELUDE` + templated body) and run it in a separate interpreter (`BENCH_PYTHON`, which must have torch; the project venv does not). The script reports back by printing a single JSON line to stdout, which `_run` parses. `.cu` files are checked with `nvcc -c`; `.py` files by importing them.

## Experiment conventions

- Tool lists and system prompts are the experimental variables. When changing them for an experiment, record the result in README "실험 기록" using its format (조건 / 과제와 판정 / 결과 / 해석) — include model, endpoint, tool composition, repeat count, and how success was judged.
- Keep agents small: one module = `SYSTEM_PROMPT` + factory. Put behavior in tools or workflows, not in agent modules.
- Role separation is a property of a **workflow**, not a repo-wide rule. Another workflow may split roles differently; document its split and the reason in README "워크플로".

## Workflows

### Accelerator optimization loop: role split

This is a deliberate role separation: `optimizer` edits code but has no measurement tools; `evaluator` measures (compile, correctness, latency) but cannot edit. A human passes results between them. Don't give either the other's capabilities. `planner` (ranks hypotheses), `reviewer` (static check before device time — so no `compile_check`), and `debugger` (diagnoses compile/correctness/regression failures; noise failures are routed to re-measurement and never reach it, so it must not invent causes that become false lessons) are read-only: they neither edit nor measure.

## Adding things

- Tool: `@tool` function in a `tools/` module → import in `tools/__init__.py` and add to the right list.
- Agent: module in `agents/` with `SYSTEM_PROMPT` + factory → re-export in `agents/__init__.py` → `_run(factory, "label")` wrapper in `cli.py` → register in `[project.scripts]`. Also update the README "카탈로그" tables and "구조" section.
- Tool list: define in `tools/__init__.py` and add it to README "카탈로그 > 도구 목록".
- Workflow: document it in README "워크플로" (flow diagram, agent and permissions per step, why roles are split that way). The code location for workflows (e.g. LangGraph graphs) is not decided yet — decide it when the first workflow is implemented in code, then record it here.

## Known model limitation (important when debugging)

The default `qwen3.5:9b` is a reasoning model; Ollama sometimes returns output only in the `reasoning` field with empty `content`, which `langchain-openai` discards, so the agent loop stops mid-task. Whether this happens varies non-monotonically with the tool list composition (documented in README "실험 기록" and "알려진 한계"). The order of `CODING_TOOLS` is intentional — don't reorder or add/remove tools expecting a fix, and don't attribute empty responses to tool bugs. The real fix is a larger or non-reasoning model via `OPENAI_MODEL`.
