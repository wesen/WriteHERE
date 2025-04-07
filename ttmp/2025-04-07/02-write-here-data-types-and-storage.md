# WriteHERE: Data Types and Storage Implementation

This document examines the data structures, storage mechanisms, and persistence systems used in the WriteHERE framework, with a focus on the backend implementation.

## 1. Core Data Structures

### 1.1 Task Graph Structure

The task graph is the central data structure in WriteHERE, implemented in `recursive/graph.py`:

```
Graph
├── graph_edges: Dict[str, List[Node]]  # Maps node IDs to child nodes
├── nid_list: List[str]                 # List of all node IDs
├── node_list: List[Node]               # List of all node objects
├── topological_task_queue: List[Node]  # Nodes in execution order
└── outer_node: Node                    # Reference to parent node
```

The graph implements a directed acyclic graph (DAG) structure where:
- Nodes represent individual tasks
- Edges represent dependencies between tasks
- The topological ordering ensures dependencies are executed in the correct order

### 1.2 Node Structure

Nodes are implemented as `AbstractNode` subclasses (primarily `RegularDummyNode`), containing:

```
AbstractNode
├── nid: str                     # Unique node identifier
├── hashkey: str                 # UUID for node instance
├── node_graph_info: Dict        # Graph context information
│   ├── outer_node: Node         # Parent node (if hierarchical)
│   ├── root_node: Node          # Root node of entire task
│   ├── parent_nodes: List[Node] # Dependency nodes
│   └── layer: int               # Hierarchical layer depth
├── task_info: Dict              # Task-specific information
│   ├── goal: str                # Task objective
│   ├── task_type: str           # Type (write/think/search)
│   ├── length: str              # For composition tasks
│   └── dependency: List[int]    # IDs of dependency tasks
├── inner_graph: Graph           # Nested subtasks graph
├── status: TaskStatus           # Current execution state
├── result: Dict                 # Task execution results
└── status_list: Dict            # State management tracking
```

This structure enables:
- Hierarchical nesting of tasks (a node can contain other nodes)
- State tracking through the task lifecycle
- Storage of task-specific information and results

### 1.3 Memory System

The `Memory` class in `recursive/memory.py` acts as a shared state repository:

```
Memory
├── root_node: Node              # Reference to root node
├── article: str                 # Accumulated written content
├── collected_info: Dict         # Cached information by node
├── format: str                  # Output format specification
└── config: Dict                 # Configuration parameters
```

This structure:
- Provides context between task executions
- Maintains the growing article text
- Caches node information to avoid recomputation

## 2. Persistence Mechanisms

### 2.1 Graph Serialization

Task graphs are serialized using both pickle and JSON formats:

```python
# In GraphRunEngine.save()
def save(self, folder):
    root_node_file = "{}/nodes.pkl".format(folder)
    root_node_json_file = "{}/nodes.json".format(folder)
    article_file = "{}/article.txt".format(folder)
    
    with open(root_node_file, "wb") as f:
        pickle.dump(self.root_node, f)
    
    with open(root_node_json_file, "w") as f:
        json.dump(self.root_node.to_json(), f, indent=4, ensure_ascii=False)
    
    self.memory.save(folder)
    
    with open(article_file, 'w', encoding='utf-8') as file:
        file.write(self.memory.article)
```

The dual serialization approach serves different purposes:
- **Pickle format**: For complete object serialization preserving all state
- **JSON format**: For human-readable exploration and visualization
- **Text format**: For the article content

### 2.2 Loading Mechanism

Graph states are loaded from disk using:

```python
# In GraphRunEngine.load()
def load(self, folder):
    root_node_file = "{}/nodes.pkl".format(folder)
    with open(root_node_file, "rb") as f:
        self.root_node = pickle.load(f)
    
    self.memory = self.memory.load(folder)
```

This enables:
- Recovery from previous execution states
- Resumption of interrupted tasks
- Inspection of completed tasks

### 2.3 Memory Persistence

The Memory system implements its own serialization:

```python
# In Memory class
def save(self, folder):
    memory_file = "{}/memory.pkl".format(folder)
    with open(memory_file, "wb") as f:
        pickle.dump(self, f)
        
@classmethod
def load(cls, folder):
    memory_file = "{}/memory.pkl".format(folder)
    with open(memory_file, "rb") as f:
        return pickle.load(f)
```

This allows:
- Preservation of the entire memory context
- Maintenance of article text and node information across sessions

## 3. Caching Systems

### 3.1 LLM Response Caching

The system implements a sophisticated caching mechanism for language model responses in `recursive/cache.py`:

```python
class Cache:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def get(self, key, default=None):
        key_hash = hashlib.md5(key.encode()).hexdigest()
        file_path = os.path.join(self.cache_dir, key_hash)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                return pickle.load(f)
        return default
        
    def set(self, key, value):
        key_hash = hashlib.md5(key.encode()).hexdigest()
        file_path = os.path.join(self.cache_dir, key_hash)
        with open(file_path, 'wb') as f:
            pickle.dump(value, f)
```

Key features:
- Uses MD5 hashing of input prompts as cache keys
- Stores serialized response objects in the filesystem
- Organized by cache type (search/llm)

### 3.2 Search Result Caching

Search results are cached in a similar mechanism to LLM responses, but in a separate cache namespace:

```python
# In report_writing function
caches["search"] = Cache("{}/../cache/{}-{}-search".format(root_folder, start, end))
caches["llm"] = Cache("{}/../cache/{}-{}-llm".format(root_folder, start, end))
```

This enables:
- Reuse of search results across runs
- Reduction in external API usage
- Faster execution for repeated searches

## 4. State Management

### 4.1 Task State Transitions

Task state is managed through the `TaskStatus` enum and state transition logic:

```python
class TaskStatus(Enum):
    NOT_READY = 1        # Dependencies not fulfilled
    READY = 2            # Ready for execution
    NEED_UPDATE = 3      # Requires update from dependencies
    FINAL_TO_FINISH = 4  # Subtasks complete, needs aggregation
    NEED_POST_REFLECT = 5 # Needs verification
    FINISH = 6           # Task complete
    PLAN_DONE = 7        # Planning phase complete
    DOING = 8            # Currently executing
    FAILED = 9           # Task failed
```

State transitions are controlled by:
- Status-action mappings that define valid actions for each state
- Status-exam mappings that define conditions for state transitions
- The `forward_exam()` method that updates states based on conditions

### 4.2 Execution State

The execution state tracking maintains:

```python
# Node states
node.status_list = {
    "silence": [],       # States where node doesn't provide outputs
    "suspend": [],       # States where node execution is paused
    "activate": []       # States where node is actively executing
}

# Status-action mappings
node.status_action_mapping = {
    # Maps status to action methods
    TaskStatus.READY: "plan",
    TaskStatus.DOING: "execute", 
    # etc.
}
```

This structure allows:
- Deterministic state transitions
- Clear separation of concerns for different execution phases
- Recovery from intermediate states

## 5. File Structure and Organization

### 5.1 Project Output Structure

When executing a writing task, the system creates a structured directory:

```
project/
├── {task_id}/
│   ├── nodes.pkl     # Serialized graph structure
│   ├── nodes.json    # Human-readable graph representation
│   ├── memory.pkl    # Serialized memory state
│   ├── article.txt   # Generated text content
│   └── done.txt      # Task completion marker
└── cache/
    ├── {start}-{end}-search/  # Search result cache
    └── {start}-{end}-llm/     # LLM response cache
```

This structure enables:
- Isolation of different writing tasks
- Clear tracking of completion status
- Efficient caching across related tasks

### 5.2 Incremental Output

The system supports incremental output through the shared memory:

```python
# In GraphRunEngine.forward_one_step_not_parallel
self.memory.update_infos([need_next_step_node])

# In Memory.update_infos
def update_infos(self, nodes):
    # Update internal state based on node changes
    # Update article text with new content
    self.article = self._compute_article()
```

This allows:
- Real-time updating of the article text
- Visualization of progress during execution
- Incremental saving of state

## 6. Data Flow in Backend Server

The backend server (`backend/server.py`) serves as an API layer over the core engine, with key data structures:

### 6.1 Task Queue Management

```python
# Task queue data structure
task_queue = {
    'task_id': {
        'engine': GraphRunEngine,        # Engine instance
        'status': 'running|done|error',  # Task status
        'result': str,                   # Final result if done
        'error': str,                    # Error message if failed
        'started_at': datetime,          # Start timestamp
        'updated_at': datetime           # Last update timestamp
    }
}
```

This structure:
- Tracks all active and completed tasks
- Maintains task metadata for status reporting
- Enables concurrent task execution

### 6.2 API Data Formats

The server exchanges data with clients using standardized JSON formats:

**Task Submission Format:**
```json
{
  "prompt": "Writing task objective",
  "mode": "story|report",
  "model": "gpt-4o|claude-3-sonnet|etc"
}
```

**Task Status Response:**
```json
{
  "task_id": "unique-task-id",
  "status": "running|done|error",
  "progress": {
    "completed_nodes": 25,
    "total_nodes": 42
  },
  "nodes": [...],  // Current task graph in JSON format
  "article": "..."  // Current article text
}
```

This standardization enables:
- Clean separation between backend and frontend
- Stateless communication
- Easy integration with various frontends

## 7. Node JSON Representation

For visualization and client interaction, nodes are serialized to JSON:

```python
# In AbstractNode.to_json
def to_json(self):
    return {
        "nid": self.nid,
        "hashkey": self.hashkey,
        "task_info": self.task_info,
        "status": self.status.name,
        "node_type": self.node_type.name if self.node_type else None,
        "result": self.result,
        "inner_graph": self.inner_graph.to_json() if hasattr(self.inner_graph, "to_json") else None
    }
```

This representation:
- Omits complex objects that can't be serialized
- Preserves task hierarchies for visualization
- Includes state information for UI updates

## 8. Memory Usage Optimization

The system implements several optimizations to manage memory usage:

### 8.1 Selective Information Collection

```python
# In Memory.collect_node_run_info
def collect_node_run_info(self, node):
    # Collect only necessary information for execution
    # Cache collected info to avoid recomputation
    if node.hashkey in self.collected_info:
        return self.collected_info[node.hashkey]
    
    # Compute and cache information
    info = self._compute_node_info(node)
    self.collected_info[node.hashkey] = info
    return info
```

This mechanism:
- Avoids collecting unnecessary information
- Caches computed information for reuse
- Reduces memory pressure during execution

### 8.2 Serialization Trade-offs

The system balances between:
- **Complete object serialization** (pickle) for exact state recovery
- **Partial serialization** (JSON) for human readability and visualization
- **Selective caching** to avoid redundant computation and API calls

## 9. Conclusion

The WriteHERE system implements a sophisticated data management approach that enables:

1. **Hierarchical task representation** through nested graph structures
2. **Flexible state management** through well-defined state transitions
3. **Efficient persistence** through multiple serialization formats
4. **Performance optimization** through multi-level caching
5. **Clean separation of concerns** between data representation and execution logic

This design ensures that complex writing tasks can be decomposed, executed, visualized, and recovered efficiently, while maintaining a clear structure that allows for extension and customization. 