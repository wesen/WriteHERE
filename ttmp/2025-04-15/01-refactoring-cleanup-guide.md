# Recursive Codebase Cleanup Guide (Phase 1: Organization & Naming)

## 1. Introduction

Welcome! This document outlines the first phase of refactoring the `recursive` codebase. The primary goal of this phase is to improve the project's structure for better readability, maintainability, and ease of navigation, especially for new developers. We will focus _only_ on renaming files/directories and splitting overly large or multi-responsibility files. No functional code changes should occur in this phase.

## 2. Guiding Principles

- **Single Responsibility Principle (SRP):** Each file should ideally contain one primary class or a set of closely related functions serving a single purpose.
- **Clear Naming:** Filenames and directory names should clearly indicate their contents or purpose. Avoid abbreviations where possible and use standard Python conventions (snake_case for files/modules).
- **Logical Grouping:** Related components (e.g., different LLM clients, specific agent types, utility functions) should be grouped together in directories.
- **Consistency:** Apply naming and organizational patterns consistently across the codebase.

## 3. Directory Structure Changes

No major directory _structure_ changes are planned in this phase, mostly renaming and splitting files _within_ the existing structure (`llm/`, `executor/`, `utils/`, `agent/`, etc.).

## 4. File Renaming Plan

| Old Path                                               | New Path                                        | Rationale                                                                                     |
| :----------------------------------------------------- | :---------------------------------------------- | :-------------------------------------------------------------------------------------------- |
| `recursive/utils/register.py`                          | `recursive/utils/registry.py`                   | More descriptive name ("registry" fits the `Register` class). Avoids name collision.          |
| `recursive/executor/actions/register.py`               | `recursive/executor/actions/action_registry.py` | Clarifies its specific purpose (registering actions). Avoids name collision.                  |
| `recursive/llm/llm.py`                                 | `recursive/llm/base.py` & specific client files | See File Splitting Plan below. `llm.py` is too generic.                                       |
| `recursive/agent/agent_base.py`                        | `recursive/agent/base.py`                       | Standard convention for base classes.                                                         |
| `recursive/executor/agents/base_agent.py`              | `recursive/executor/agents/base.py`             | Standard convention for base classes.                                                         |
| `recursive/executor/actions/base_action.py`            | `recursive/executor/actions/base.py`            | Standard convention for base classes.                                                         |
| `recursive/executor/actions/selector_and_summazier.py` | `recursive/executor/actions/summarizer.py`      | Corrects typo ("summazier") and shortens name. Assumes summarization is the primary function. |

## 5. File Splitting Plan

| Original File                       | New Files & Contents                                                                                                                                                                                                                                                                                                                                                                                 | Rationale                                                                                                                                                                                                                 |
| :---------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `recursive/cache.py`                | - `recursive/cache.py`: Keep `Cache` class. <br> - `recursive/utils/helpers.py`: Move `string_to_md5`, `json_default_dumps`, `obj_to_hash`, `get_datatime`, `get_omit_json`.                                                                                                                                                                                                                         | Separates the core `Cache` class from general utility/helper functions. Consolidates helpers in `utils`.                                                                                                                  |
| `recursive/utils/file_io.py`        | - `recursive/utils/file_io.py`: Keep file I/O functions (`read_*`, `write_*`, `ensure_dir`, etc.). <br> - `recursive/utils/parsing.py`: Move `parse_hierarchy_tags_result`, `parse_tag_result`.                                                                                                                                                                                                      | Separates file system operations from data parsing logic, improving focus for each module.                                                                                                                                |
| `recursive/graph.py`                | - `recursive/graph.py`: Keep `Graph` class. <br> - `recursive/common/enums.py` (New dir): Move `TaskStatus`, `NodeType`. <br> - `recursive/nodes.py`: Move `AbstractNode`, `RegularDummyNode`. <br> - `recursive/utils/helpers.py`: Move `process_all_node_to_node_str`.                                                                                                                             | Decomposes a very large file (800+ lines) into logical components: graph structure, node definitions, and common enumerations. Moves helper to `utils`. Creates a `common` dir for shared elements like enums.            |
| `recursive/agent/agents/regular.py` | - `recursive/agent/agents/regular.py`: Keep `RegularAgent` class. <br> - `recursive/agent/agents/helpers.py`: Move `get_llm_output` function.                                                                                                                                                                                                                                                        | Separates the main agent class from its helper/utility function. Improves readability of the agent file.                                                                                                                  |
| `recursive/llm/llm.py`              | - `recursive/llm/base.py`: Move `BaseLLM`. <br> - `recursive/llm/openai.py`: Move `OpenAIApiProxy`. <br> - `recursive/llm/claude.py`: Move `ClaudeApiProxy`. <br> - `recursive/llm/qwen.py`: Move `QwenApiProxy`. <br> - `recursive/llm/gemini.py`: Move `GeminiApiProxy`. <br> - `recursive/llm/ollama.py`: Move `OllamaApiProxy`. <br> - `recursive/llm/xinference.py`: Move `XinferenceApiProxy`. | Original file contained too many distinct LLM client implementations. Splitting allows easier management and addition/removal of specific clients. Renames original to `base.py` and creates specific files per provider. |

## 6. Target Structure (Conceptual)

```
recursive/
├── __init__.py
├── agent/
│   ├── __init__.py
│   ├── base.py              # Renamed from agent_base.py
│   ├── proxy.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── regular.py       # Split from original regular.py
│   │   └── helpers.py       # New file split from regular.py
│   └── prompts/
│       ├── __init__.py
│       ├── base.py
│       ├── report/
│       ├── search_agent/
│       └── story_writing_wo_search_nl_version_english/
├── api_key.env
├── api_key.env.example
├── cache.py                 # Split, now only contains Cache class
├── common/                  # New directory
│   └── enums.py             # New file split from graph.py
├── engine.py
├── executor/
│   ├── __init__.py
│   ├── schema.py
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── action_executor.py
│   │   ├── action_registry.py # Renamed from register.py
│   │   ├── base.py          # Renamed from base_action.py
│   │   ├── bing_browser.py
│   │   ├── builtin_actions.py
│   │   ├── parser.py
│   │   └── summarizer.py    # Renamed from selector_and_summazier.py
│   └── agents/
│       ├── __init__.py
│       ├── base.py          # Renamed from base_agent.py
│       └── claude_fc_react.py
├── graph.py                 # Split, now only contains Graph class
├── llm/
│   ├── __init__.py
│   ├── base.py              # New file split from llm.py
│   ├── claude.py            # New file split from llm.py
│   ├── gemini.py            # New file split from llm.py
│   ├── ollama.py            # New file split from llm.py
│   ├── openai.py            # New file split from llm.py
│   ├── qwen.py              # New file split from llm.py
│   └── xinference.py        # New file split from llm.py
├── memory.py
├── nodes.py                 # New file split from graph.py
├── README.md
├── test_run_report.sh
├── test_run_story.sh
└── utils/
    ├── __init__.py
    ├── display.py
    ├── file_io.py           # Split, now only contains file I/O
    ├── get_index.py
    ├── helpers.py           # New file split from cache.py and graph.py
    ├── parsing.py           # New file split from file_io.py
    └── registry.py          # Renamed from register.py

```

_(Note: `__pycache__` directories are omitted for clarity)_

## 7. Next Steps (Future Phases)

Once this organizational refactoring is complete and verified, subsequent phases will involve:

- Adding comprehensive type hints.
- Improving and standardizing docstrings.
- Writing unit and integration tests.
- Refactoring complex logic within large classes/functions.
- Updating the main `README.md`.

Please follow this guide carefully for the initial file structure cleanup. Test thoroughly after making changes to ensure no functionality is broken.
