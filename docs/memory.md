# Memory

This document describes how Kairos Mesh agents store and access information — both within a single run and across runs.

---

## Summary

- Each agent gets its own isolated `InMemoryMemory` instance for the duration of a run.
- Memory is discarded when the run ends. Nothing is carried forward to future runs.
- PostgreSQL stores a complete audit trail per run, but that data is never read back into LLM inference.
- There is no RAG system, no vector store, and no outcome-based learning loop.

---

## 1. In-run memory (transient)

Each agent is constructed at the start of a run using a factory function in `backend/app/services/agentscope/agents.py`. Every factory call passes a freshly constructed `InMemoryMemory()` to the `ReActAgent`:

```python
from agentscope.memory import InMemoryMemory

def _build_agent(name, model, formatter, toolkit, sys_prompt, ...):
    return ReActAgent(
        name=name,
        sys_prompt=sys_prompt,
        model=model,
        ...
        memory=InMemoryMemory(),
        ...
    )
```

`InMemoryMemory` stores the agent's conversation history in process memory: the system prompt, any tool calls the agent makes, and the LLM responses. This buffer exists only within the lifetime of the agent object, which is scoped to a single call to `AgentScopeRegistry.execute()` in `backend/app/services/agentscope/registry.py`.

**Agents do not share memory.** The eight pipeline agents (technical-analyst, news-analyst, market-context-analyst, bullish-researcher, bearish-researcher, trader-agent, risk-manager, execution-manager) — i.e. the agents registered in `ALL_AGENT_FACTORIES` in `backend/app/services/agentscope/agents.py` — each have their own isolated `InMemoryMemory` instance. One agent cannot read another agent's conversation buffer. (Additional agents such as `strategy-designer`, `order-guardian`, and `schedule-planner-agent` exist in the same file but are not part of the trading pipeline and are not discussed in this document.)

After `execute()` returns, the agent objects go out of scope and their memory is garbage collected. There is no explicit flush, no serialization, and no persistence of the in-memory conversation history.

---

## 2. No cross-run memory

Each run starts cold. The following mechanisms are **not implemented**:

- No RAG (retrieval-augmented generation)
- No vector store
- No embedding of past run outputs
- No feedback loop from trade outcomes (profit/loss, slippage, fill quality) back to agent prompts or weights
- No adaptive behavior based on historical performance
- No fine-tuning pipeline

The only inputs to each run are:

1. The system prompt for each agent (loaded from the DB or defaults at runtime)
2. Live market data fetched at run time (price snapshot, OHLC bars, news headlines)
3. Structured outputs passed explicitly between agents within the same run (see section 4)

---

## 3. Persistent storage (audit log, not a learning store)

PostgreSQL holds a complete record of every run, but this data is used for human review and audit — it is never read back into LLM inference.

### `analysis_runs` — `backend/app/db/models/run.py`

One record per pipeline execution. Stores:

- `pair`, `timeframe`, `mode` (simulation vs. live), `status`, `progress`
- `decision` — JSON blob of the final trading decision
- `trace` — JSON blob of intermediate pipeline state
- `error` — error message if the run failed (null on success)
- `created_at`, `started_at`, `updated_at`

### `agent_steps` — `backend/app/db/models/agent_step.py`

One record per agent per run. Stores:

- `agent_name`, `status`
- `input_payload` — what was passed into the agent
- `output_payload` — the agent's structured output and tool results; may also include timing data depending on what the pipeline writes into the JSON blob
- `error` — populated on failure

Steps are written via a single deferred commit at the end of the run (`_flush_pending_steps()`).

### `llm_call_logs` — `backend/app/db/models/llm_call_log.py`

One record per LLM API call. Stores provider, model, token counts, cost estimate, latency, and error text. No prompt content or completion text is stored here.

### `execution_orders` — `backend/app/db/models/execution_order.py`

One record per trade order submitted to the broker. Stores symbol, side, volume, mode, request/response payloads, and status.

All four tables are queryable by operators for inspection, debugging, and compliance review. None of their contents are read by the pipeline on subsequent runs.

---

## 4. What IS passed between agents within a run

Agents do not share memory, but structured outputs are passed explicitly between phases. This is data passing via function arguments, not shared memory.

**Phase 1 → Phase 2+3 (debate):**

After the three analysts complete, their text outputs are concatenated into `analysis_summary` and passed as a new `Msg` to the bullish and bearish researchers:

```python
research_msg = Msg("system",
    f"Analysis results from Phase 1:\n{analysis_summary}\n\n"
    f"Original context:\n{context_msg.get_text_content()}", "system")
```

The researcher toolkits are also rebuilt with `analysis_outputs` so that the `evidence_query` tool can reference Phase 1 findings.

**Phase 2+3 → Phase 4 (trader):**

Debate result fields (`winner`, `conviction`, `key_argument`, `weakness`) are injected into the prompt variables dictionary (`base_vars`) before the trader-agent is called. The trader receives this as part of its rendered user prompt, not as a memory object.

**Trader → Risk manager → Execution manager:**

The trader's structured output (`trader_out`) is passed as an argument to the risk manager's tool (`risk_evaluation`, `position_size_calculator`). The risk manager's output (`risk_out`) is then passed to the execution manager's tools. Both are passed through `_call_agent()` and `_build_prompt_variables()`.

In all cases the mechanism is explicit argument passing within a single Python coroutine (`execute()`). It is not shared memory, a message bus, or a blackboard.

---

## 5. Limitations

The following are explicit design constraints, not implementation gaps to be resolved:

- **No outcome-based learning.** Whether a trade is profitable or not has no effect on any future run. There is no mechanism to record outcomes and adjust agent behavior.
- **No adaptive prompts.** System prompts are static per run. They can be edited by an operator in the DB between runs, but the pipeline does not modify them automatically.
- **No inter-agent memory within a run.** Agents cannot read each other's `InMemoryMemory`. Information sharing is limited to the explicit structured outputs described in section 4.
- **DB logs are not used in inference.** The `agent_steps`, `llm_call_logs`, and `execution_orders` tables are queryable by humans but are never fetched and injected into LLM context.
- **No compression or summarization of past runs.** There is no job that summarizes past run outcomes and prepends them to future prompts.

The design prioritizes determinism, auditability, and operational simplicity over adaptive behavior.
