# WriteHERE: Report Writing Task-to-Prompt Mapping and Base Type Analysis

## Overview

This document explains how report writing tasks in WriteHERE are mapped to specific prompt templates, and how these prompts are associated with the core base types: **COMPOSITION**, **REASONING**, and **RETRIEVAL**. The analysis is based on the code in `recursive/agent/agents/regular.py`, the prompt implementations in `recursive/agent/prompts/report/`, and the configuration logic in `recursive/engine.py`. It references the overall architecture documentation ([01-write-here-architecture-report.md](../2025-04-07/01-write-here-architecture-report.md), [01-system-overview.md](../step-by-step/01-system-overview.md)).

---

## 1. Task Types and Base Types

WriteHERE organizes all tasks under three base types:

- **COMPOSITION**: Writing tasks ("write")
- **REASONING**: Analytical tasks ("think")
- **RETRIEVAL**: Information gathering/search tasks ("search")

These are mapped in the config as:

```python
"task_type2tag": {
    "COMPOSITION": "write",
    "REASONING": "think",
    "RETRIEVAL": "search",
},
```

Each node in the task graph has a `task_type` (e.g., COMPOSITION) and a tag (e.g., "write").

---

## 2. Configuration: Mapping Tasks to Prompts

The mapping from task type and action (e.g., execute, atom, planning) to prompt is defined in the `config` dictionary (see `report_writing()` in `engine.py`). For report writing, the relevant section is:

```python
"COMPOSITION": {
    "execute": {"prompt_version": "ReportWriter", ...},
    "atom": {
        "without_update_prompt_version": "ReportAtom",
        "with_update_prompt_version": "ReportAtomWithUpdate",
        ...
    },
    "planning": {"prompt_version": "ReportPlanning", ...},
    ...
},
"RETRIEVAL": {
    "execute": {"prompt_version": "SearchAgentENPrompt", ...},
    "search_merge": {"prompt_version": "MergeSearchResultVFinal", ...},
    "atom": {"prompt_version": "ReportSearchOnlyUpdate", ...},
    ...
},
"REASONING": {
    "execute": {"prompt_version": "ReportReasoner", ...},
    ...
},
```

Each action ("execute", "atom", "planning", etc.) for a base type is mapped to a `prompt_version`, which is the name of a prompt class in the `recursive/agent/prompts/report/` directory.

---

## 3. Prompt Class Implementations

The prompt classes are registered and used via the `prompt_register` system. Key prompt classes for report writing include:

- **COMPOSITION**
  - `ReportWriter` (execute): Main writing prompt
  - `ReportAtom`, `ReportAtomWithUpdate` (atom): For atomicity and goal updating
  - `ReportPlanning` (planning): For recursive decomposition of writing tasks
- **REASONING**
  - `ReportReasoner` (execute): For analytical sub-tasks
- **RETRIEVAL**
  - `SearchAgentENPrompt` (execute): For search agent (external search)
  - `MergeSearchResultVFinal` (search_merge): For merging search results
  - `ReportSearchOnlyUpdate` (atom): For updating search task goals

Each prompt class defines a system message and a content template, specifying the instructions and output format for the LLM.

---

## 4. How Prompts Are Selected at Runtime

The agent logic in `regular.py` (see `get_llm_output`) selects the prompt version based on:

- The node's `task_type` (COMPOSITION, REASONING, RETRIEVAL)
- The current action ("execute", "atom", "planning", etc.)
- The node's config (which may specify different prompts for different situations, e.g., with/without update)

Example logic:

```python
if agent_type == "planning":
    prompt_version = inner_kwargs["prompt_version"]
elif agent_type == "atom":
    if inner_kwargs.get("update_diff", False):
        if len(node.node_graph_info["parent_nodes"]) > 0:
            prompt_version = inner_kwargs["with_update_prompt_version"]
        else:
            prompt_version = inner_kwargs["without_update_prompt_version"]
    else:
        prompt_version = inner_kwargs["prompt_version"]
else:
    prompt_version = inner_kwargs["prompt_version"]
```

The selected `prompt_version` is then used to instantiate the corresponding prompt class and generate the LLM prompt.

---

## 5. Mapping Table: Task Type, Action, and Prompt

| Base Type   | Action       | Prompt Class                      | File                                    |
| ----------- | ------------ | --------------------------------- | --------------------------------------- |
| COMPOSITION | execute      | ReportWriter                      | report/writer.py                        |
| COMPOSITION | atom         | ReportAtom / ReportAtomWithUpdate | report/write_combine_atom_and_update.py |
| COMPOSITION | planning     | ReportPlanning                    | report/full_planning.py                 |
| REASONING   | execute      | ReportReasoner                    | report/reasoner.py                      |
| RETRIEVAL   | execute      | SearchAgentENPrompt               | search_agent/main.py                    |
| RETRIEVAL   | search_merge | MergeSearchResultVFinal           | report/merge_search_result.py           |
| RETRIEVAL   | atom         | ReportSearchOnlyUpdate            | report/search_only_update.py            |

---

## 6. Example: COMPOSITION Task Flow

1. **Planning**: The root node (COMPOSITION) is decomposed using `ReportPlanning`.
2. **Atom**: Each sub-task is checked for atomicity/goal update using `ReportAtom` or `ReportAtomWithUpdate`.
3. **Execute**: Atomic writing tasks are executed using `ReportWriter`.

## 7. Example: RETRIEVAL Task Flow

1. **Atom**: Search task goal is updated using `ReportSearchOnlyUpdate`.
2. **Execute**: Search is performed using `SearchAgentENPrompt` (external search agent).
3. **Merge**: Results are merged using `MergeSearchResultVFinal`.

## 8. Example: REASONING Task Flow

1. **Execute**: Analytical sub-tasks are executed using `ReportReasoner`.

---

## 9. Summary Table: Prompt-to-Base-Type Mapping

| Prompt Class            | Base Type   |
| ----------------------- | ----------- |
| ReportWriter            | COMPOSITION |
| ReportAtom              | COMPOSITION |
| ReportAtomWithUpdate    | COMPOSITION |
| ReportPlanning          | COMPOSITION |
| ReportReasoner          | REASONING   |
| SearchAgentENPrompt     | RETRIEVAL   |
| MergeSearchResultVFinal | RETRIEVAL   |
| ReportSearchOnlyUpdate  | RETRIEVAL   |

---

## 10. References

- [01-write-here-architecture-report.md](../2025-04-07/01-write-here-architecture-report.md)
- [01-system-overview.md](../step-by-step/01-system-overview.md)
- `recursive/engine.py` (config and task flow)
- `recursive/agent/agents/regular.py` (agent logic)
- `recursive/agent/prompts/report/` (prompt implementations)

---

## 11. Conclusion

Report writing in WriteHERE is driven by a clear mapping from high-level task types (COMPOSITION, REASONING, RETRIEVAL) to specific prompt templates, with each prompt tailored to the requirements of its action and base type. This mapping is defined in the configuration and enforced at runtime by the agent logic, ensuring that each sub-task receives the correct instructions and output format for the LLM. The modular prompt system enables flexible, recursive, and heterogeneous planning for complex report generation tasks.
