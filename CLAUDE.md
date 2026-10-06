# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`agent-lab`: a repo for experimenting with LLM agent designs by combining tools, agents, and workflows. Built on LangChain `create_agent`, talking to any OpenAI-compatible endpoint. `OPENAI_BASE_URL` and `OPENAI_MODEL` have no defaults, and the repo is not tied to any server or model — keep README and examples endpoint-neutral; model/endpoint specifics belong only in README "실험 기록" entries.

Three layers, a benchmark harness on top, plus a record of results:
- **Tool** — a `@tool` function in `tools/`. The smallest part.
- **Agent** — a system prompt plus a tool list, in `agents/`. Currently nine: `agent` (general assistant), `researcher`, `npu_researcher`, `coder`, and `planner`, `optimizer`, `reviewer`, `evaluator`, `debugger`.
- **Workflow** — how agents are chained. Each workflow is a directory `workflows/<name>/`, documented in its `README.md` (human-chained ones have only the `README.md`), and README "워크플로" is just an index table.
- **Benchmark** — `benchmarks/`: runs a workflow over a public problem set and scores the candidates with that benchmark's official scorer. Currently KernelBench.
- **Experiment record** — README "실험 기록": which combination produced which result.

Everything user-facing — system prompts, tool docstrings, tool return strings, comments, README, commit messages — is written in Korean; keep it that way.

## Commands

```bash
uv sync                                   # install (Python 3.13, uv)
uv run agent "질문"                        # one-shot: answer and exit
uv run coder                              # no args: interactive REPL (Ctrl-D to quit)
WORKSPACE_ROOT=~/proj uv run coder "..."  # file/shell/bench tools operate under WORKSPACE_ROOT
WORKSPACE_ROOT=~/kernels uv run kernel-opt-oneshot slow.py "요청"  # run a workflow
uv run kernelbench 1 1-3 --workflow oneshot  # run a workflow over KernelBench level 1, problems 1-3
```

Entry points are `[project.scripts]` in `pyproject.toml` → functions in `cli.py`. There is no test suite, linter, or formatter configured. Verify changes by running the relevant agent against a real endpoint.

Config comes from env vars or `.env` (env vars win). `OPENAI_BASE_URL` and `OPENAI_MODEL` are required: `build_llm()` raises `ConfigError` when either is missing or empty, and `cli.py` turns it into an exit message. Optional: `OPENAI_API_KEY`, `DOCS_ROOT`, `NPU_WIKI_ROOT` (required only by `npu-researcher`; missing → `ConfigError`), `WORKSPACE_ROOT`, `BENCH_PYTHON`, `TRACE`, `TRACE_DIR`, `KERNELBENCH_ROOT` (required only by `kernelbench`; missing → `ConfigError`), `KERNELBENCH_PYTHON` (falls back to `BENCH_PYTHON`). See `.env.example`.

## Architecture

- `llm.py` — `build_llm(model=None)` returns a `ChatOpenAI` with `temperature=0`; `model` overrides `OPENAI_MODEL` (the endpoint stays shared). Env is read at import time.
- `agents/base.py` — `build(system_prompt, tools, model=None, name=None)` wraps `create_agent` with an `InMemorySaver` checkpointer (conversation memory lives only within the process); `name` is the agent's name in trace logs (`ask` reads it back with `agent.get_name()`, which also works through `.with_config()`). `ask(agent, question, thread_id)` runs inside `tracing.asking(...)`, invokes the agent, strips everything before the last `</think>`, and if the final content is empty, falls back to listing the `ToolMessage`s from the current turn (`_current_turn` slices after the last `HumanMessage`, since the checkpointer returns prior turns too).
- `tracing.py` — JSONL trace log, on by default (`TRACE=0` disables, `TRACE_DIR` defaults to `<project>/traces/`, gitignored), one file per process opened on the first event. Two layers joined by a `ContextVar` holding the current `Ask`: `asking()` writes `ask`/`answer` events and sets `parent`/`caller` from the enclosing ask (LangGraph copies context into tool and parallel-node threads, so subagent calls nest correctly); `http_client()` is an `openai.DefaultHttpxClient` with event hooks that `build_llm` passes to `ChatOpenAI`, writing one `llm` event per HTTP call with the raw request/response bodies (so the `reasoning` field that `langchain-openai` drops is kept) and adding `usage` to the current ask. Use `DefaultHttpxClient`, not a bare `httpx.Client` (5 s timeout). Env is read lazily because `llm.py` imports it before `load_dotenv()`. Writes are under a lock (oneshot branches run in parallel). `mark(label, **fields)` records boundaries (`run_suite` marks each problem).
- `agents/<name>.py` — each is just a `SYSTEM_PROMPT` plus a `build_<name>()` factory calling `build(SYSTEM_PROMPT, <TOOL_LIST>, name="<name>")`. Re-exported from `agents/__init__.py`.
- `tools/__init__.py` — calls `load_dotenv()` **before** importing tool modules, because modules like `tools/workspace.py` and `tools/bench.py` read env vars at import time. Defines the per-agent lists: `TOOLS`, `RESEARCH_TOOLS`, `NPU_RESEARCH_TOOLS`, `CODING_TOOLS`, `OPTIMIZE_TOOLS` (= `CODING_TOOLS`), `EVALUATE_TOOLS`, and `PLAN_TOOLS`/`REVIEW_TOOLS`/`DEBUG_TOOLS` (all = read-only `READ_TOOLS`).
- `tools/workspace.py` — `ROOT` from `WORKSPACE_ROOT`; when unset or empty it defaults to `<project>/workspace/` (created on import, gitignored) so agents don't edit the project source by default; `resolve()` returns `None` for paths escaping the root, and every file tool in `code.py`/`bench.py` must check that. `run_command` (`tools/shell.py`) is a raw shell with `cwd=ROOT` and is **not** sandboxed.
- `tools/npu_wiki.py` — `search_wiki`/`read_wiki_page` over a KernelWiki-style NPU wiki at `NPU_WIKI_ROOT` (markdown + minimal frontmatter parser, no PyYAML). It must not fail at import, since every agent imports `tools`; `build_npu_researcher()` calls `require_root()`, which raises `ConfigError`. `NPU_RESEARCH_TOOLS` deliberately has no web tools (internal terms must not leak into search queries, and it isolates the wiki's effect). It is a separate agent so `researcher`/`RESEARCH_TOOLS` stay unchanged as an experimental variable.
- `tools/bench.py` — `benchmark`, `compare_outputs`, `compile_check` generate a Python script (a `_PRELUDE` + templated body) and run it in a separate interpreter (`BENCH_PYTHON`, which must have torch; the project venv does not). The script reports back by printing a single JSON line to stdout, which `_run` parses. `.cu` files are checked with `nvcc -c`; `.py` files by importing them. `_run(script, python=BENCH_PYTHON)` takes the interpreter as an argument so benchmark adapters can reuse it with their own.

## Benchmarks

- `benchmarks/suite.py` — `run_suite(title, problems, score, workflow, request)`: per `Problem`, deletes stale `<name>_opt*` files, runs the workflow (`WORKFLOWS`: `orchestrator`/`oneshot`; exceptions are recorded, not raised), then scores **every** `<name>_opt*` with the adapter's `score(reference, candidate) -> Score`, keeps the fastest correct one, aggregates (correct rate, fast_0, fast_1, geomean speedup), and writes a report to `WORKSPACE_ROOT/benchmarks/`.
- Scoring is done by the harness in code, **not** by an agent tool, on purpose: agents' tool lists and prompts stay unchanged, so workflow/model comparisons keep the same experimental variables. Don't add benchmark scorers to `EVALUATE_TOOLS`.
- One adapter per benchmark (problem/candidate/result formats differ, e.g. KernelBench = one `.py` per problem, FlashInfer-Bench = definition JSON + many workloads). Shared code is only `suite.py`. Each benchmark gets its own interpreter variable (`<NAME>_PYTHON`, fallback `BENCH_PYTHON`) since pinned versions conflict.
- `benchmarks/kernelbench.py` — pinned to KernelBench commit `423217d9…` (`kernelbench.eval.eval_kernel_against_ref`). Problems are copied to `kernelbench/l<level>_p<id>.py` (original names start with a digit and can't be imported). If a candidate has no `ModelNew` but has `class Model`, `ModelNew = Model` is appended — existing workflows tell the optimizer to keep the original name, and this avoids changing their prompts. Candidates containing `import triton` use `backend="triton"`. KernelBench's own stdout is redirected to stderr so `_run` sees only the JSON line.

## Experiment conventions

- Tool lists and system prompts are the experimental variables. When changing them for an experiment, record the result in README "실험 기록" using its format (조건 / 과제와 판정 / 결과 / 해석) — include model, endpoint, tool composition, repeat count, and how success was judged.
- Keep agents small: one module = `SYSTEM_PROMPT` + factory. Put behavior in tools or workflows, not in agent modules.
- Role separation is a property of a **workflow**, not a repo-wide rule. Another workflow may split roles differently; document its split and the reason in its `workflows/<name>/README.md`.

## Workflows

- `workflows/<name>/` — a package per workflow. `build_<name>()` assembles a `StateGraph` (or, for an agent-driven workflow, returns the orchestrating agent); `run_<name>(...)` invokes it and returns a report string. Nodes build agents via `agents` factories (once per graph build) and call `ask(agent, question, thread_id)`. Both are re-exported from `workflows/<name>/__init__.py`, then from `workflows/__init__.py`. How a workflow splits into modules is up to that workflow (`kernel_opt_oneshot` keeps everything in `graph.py`; `kernel_opt_orchestrator` splits into `orchestrator.py` and `subagents.py`).
- Agent memory is keyed by `thread_id`: reuse a thread id to let an agent continue its own conversation across nodes; use distinct ids for parallel branches.

### `kernel_opt_oneshot`: GPU kernel optimization (one-shot, non-interactive)

`plan` (planner) → `research` (researcher) → `select` (planner, same thread as `plan`) → `Send` fan-out of 2 → per-branch subgraph `optimize` (optimizer) → `review` (reviewer) → END. Things that are easy to break:
- The branch subgraph uses `output_schema=BranchOutput` exposing only `results` (an `operator.add` reducer). Both branches write to the parent in the same step, so any other shared key would raise `InvalidUpdateError`.
- Each branch writes to `<stem>_opt<i><suffix>` so parallel optimizers don't overwrite each other.
- researcher's tools can't read `WORKSPACE_ROOT`, so the node reads the kernel source itself and inlines it.
- Branches are picked by parsing planner's `N. [대상] ...` items (`_top_items`), tolerating markdown decoration (`**`, `#`) and ignoring numbered lists without `[대상]` — planner often appends a "다음 단계" list that a plain `^\d+\.` match would pick up. Changing planner's report format breaks this. Fewer than 2 raises with the ranking text.

### `kernel_opt_orchestrator`: one orchestrator agent + three subagents

No `StateGraph`: the orchestrator's own tool-calling loop is the optimization loop. Its only tools are `research`, `optimize`, `evaluate` (`subagents.py`), each wrapping an existing agent (`researcher`, `optimizer`, `evaluator`) via `ask()`. The orchestrator's `SYSTEM_PROMPT` lives in the workflow (`orchestrator.py`), not in `agents/`, because it is unusable without those tools. Things that are easy to break:
- The subagent tools must stay in the workflow package: `agents/*` import `tools`, so putting them in `tools/` creates an import cycle.
- Each subagent call gets a fresh `thread_id` and each round writes a new `<stem>_opt<round><suffix>` file — optimizer has been observed to stall when asked to continue editing an existing file. The orchestrator must therefore pass everything a subagent needs in the tool arguments.
- `research` reads the kernel source itself and inlines it (researcher can't read `WORKSPACE_ROOT`).
- `_delegate` turns a subagent exception into a returned string so one failing tool doesn't kill the loop. (`web_search` used to be the example: ddgs raises `DDGSException` on zero results instead of returning `[]`; it now catches that and returns a "change the query" string.)
- `run_kernel_opt_orchestrator` appends the raw delegation log (tool args + subagent answers, read back from the checkpointer) after the orchestrator's summary. That log, not the summary, is the source of truth for measured numbers — keep it.
- LangGraph's default recursion limit is effectively unbounded (10007), so `RECURSION_LIMIT` is the only code-level stop; `MAX_ROUNDS` is only a prompt instruction.

### Accelerator optimization loop (human-chained): role split

This is a deliberate role separation: `optimizer` edits code but has no measurement tools; `evaluator` measures (compile, correctness, latency) but cannot edit. A human passes results between them. Don't give either the other's capabilities. `planner` (ranks hypotheses), `reviewer` (static check before device time — so no `compile_check`), and `debugger` (diagnoses compile/correctness/regression failures; noise failures are routed to re-measurement and never reach it, so it must not invent causes that become false lessons) are read-only: they neither edit nor measure.

## Adding things

- Tool: `@tool` function in a `tools/` module → import in `tools/__init__.py` and add to the right list.
- Agent: module in `agents/` with `SYSTEM_PROMPT` + factory passing `name=` → re-export in `agents/__init__.py` → `_run(factory, "label")` wrapper in `cli.py` → register in `[project.scripts]`. Also update the README "카탈로그" tables and "구조" section.
- Tool list: define in `tools/__init__.py` and add it to README "카탈로그 > 도구 목록".
- Workflow: package `workflows/<name>/` with `build_<name>()` + `run_<name>()` → re-export in `workflows/<name>/__init__.py` and `workflows/__init__.py` → wrapper in `cli.py` → register in `[project.scripts]`. Document it in `workflows/<name>/README.md` (flow diagram, agent per node, design reasons, run example) and add one row to the README "워크플로" table. Keep per-workflow detail out of README.
- Benchmark: adapter `benchmarks/<name>.py` (prepare `Problem`s under `WORKSPACE_ROOT`, a `score` function returning `Score`, call `run_suite`) → re-export in `benchmarks/__init__.py` → `cli.py` command → `[project.scripts]`. Update README "벤치마크" and the settings table.

## Keeping docs in sync

After any change, check whether it makes something in README, CLAUDE.md, `workflows/<name>/README.md`, or `.env.example` stale, or adds something users need to know: a new or removed setting, a changed default, new error behavior, a new parameter meant to be used, or a changed command. Update those docs in the same commit, and report which docs you updated (or that none needed it). README is for users: describe how to use the change, not how it is implemented. Experiment records describe past runs; don't rewrite them to match current code.

## Known model limitation (important when debugging)

With reasoning models, some servers return output only in the `reasoning` field with empty `content`, which `langchain-openai` discards, so the agent loop stops mid-task. Observed with `qwen3.5:9b` on Ollama, where whether it happens varies non-monotonically with the tool list composition (README "실험 기록"; general description in "알려진 한계"). The order of `CODING_TOOLS` is intentional — don't reorder or add/remove tools expecting a fix, and don't attribute empty responses to tool bugs. Check the trace log for empty-`content` responses first; the real fix is a different model via `OPENAI_MODEL`.
