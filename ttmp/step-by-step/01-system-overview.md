# WriteHERE Recursive Engine: System Overview

## Introduction

WriteHERE is a sophisticated recursive task planning and execution framework designed to help large language models (LLMs) produce more coherent, well-structured documents. Unlike simpler LLM frameworks that use a single prompt for generation, WriteHERE employs a recursive decomposition strategy that mirrors how human writers approach complex writing tasks.

This guide provides a high-level overview of the system architecture to help developers understand the key components and how they interact.

## System Architecture

At its core, WriteHERE implements a hierarchical state machine where tasks are represented as nodes in a directed acyclic graph (DAG). The execution of these tasks is governed by state transitions and agent-based processing. The system follows these key steps:

1. Breaking down a large writing task into logical sections
2. Decomposing sections into specific research, reasoning, and writing tasks
3. Executing atomic tasks and synthesizing results upward

The architecture consists of four main components:

### 1. Node System

Each writing task is represented as a `Node` in a graph structure. Nodes contain:

- A state (`TaskStatus`: NOT_READY, READY, DOING, etc.)
- Action mappings (what function to call in each state)
- State transition mappings (when to change states)
- Task information (goal, type, dependencies)
- Potentially an inner graph of subtasks

The Node System is responsible for:

- Representing the hierarchical structure of tasks and subtasks
- Managing task dependencies
- Executing the state machine transitions

### 2. Agent System

Agents are specialized modules that perform specific actions on nodes:

- `UpdateAtomPlanningAgent`: Decomposes tasks into subtasks
- `SimpleExecutor`: Performs the actual writing/thinking/searching
- `FinalAggregateAgent`: Synthesizes results from subtasks
- Reflection agents: Evaluate and potentially revise execution

The Agent System is responsible for:

- Interfacing with the LLM
- Processing node tasks based on their type
- Interpreting LLM responses into structured forms

### 3. Memory System

A shared state repository that:

- Tracks the growing document
- Caches node information
- Provides context between executions

The Memory System is responsible for:

- Maintaining state across execution steps
- Providing context for agent operations
- Assembling the final document from individual task results

### 4. Execution Engine

The execution engine orchestrates the entire process:

- Finds nodes ready for action based on their state
- Performs the appropriate action via an agent
- Updates node states
- Serializes progress

## Execution Flow

The typical execution flow follows these steps:

1. **Initialization**: A root node is created representing the overall writing task
2. **Planning**: The root node is decomposed into subtasks
3. **Execution Loop**:
   - Find a node ready for action
   - Update memory with context
   - Execute the appropriate action via an agent
   - Update node states
4. **Result Aggregation**: When subtasks complete, their results are synthesized
5. **Completion**: When all tasks are complete, the final document is returned

## Launch Configuration

To debug the system, add this configuration to your `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug WriteHERE Engine",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/recursive/engine.py",
      "args": [
        "--filename",
        "../test_data/qa_test.jsonl",
        "--output-filename",
        "project/qa/example_claude/test_output/result.jsonl",
        "--done-flag-file",
        "project/qa/example_claude/test_output/done.txt",
        "--model",
        "claude-3-5-sonnet-20241022",
        "--engine-backend",
        "google",
        "--mode",
        "report"
      ],
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

## Further Reading

For deeper understanding of specific components, refer to these guides:

1. [Node System and State Machine](02-node-system.md): Details on how tasks are represented and how their states are managed
2. [Agent System](03-agent-system.md): How specialized modules interface with the LLM to process tasks
3. [Memory and Context Management](04-memory-system.md): How information is stored and shared between nodes
4. [Task Planning and Decomposition](05-task-planning.md): How high-level tasks are broken down into manageable subtasks
5. [Task Execution](06-task-execution.md): How atomic tasks are carried out
6. [Result Aggregation](07-result-aggregation.md): How subtask results are combined into coherent output
7. [Debugging Workflow](08-debugging-workflow.md): Step-by-step approach to debugging the system
