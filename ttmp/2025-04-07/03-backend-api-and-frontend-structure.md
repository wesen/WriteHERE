# WriteHERE: Backend API and Frontend Structure

This document provides a detailed analysis of the API architecture and frontend implementation of the WriteHERE system, focusing on communication patterns, state management, visualization techniques, and user controls.

## 1. Backend API Architecture

### 1.1 API Server Implementation

The WriteHERE backend API is implemented using Flask (`backend/server.py`) and exposes both RESTful endpoints and WebSocket connections for real-time updates. The API serves as a bridge between the frontend and the core engine, handling task management, execution, and reporting.

Key components of the backend API:
- **Flask REST API**: Handles standard HTTP requests
- **Flask-SocketIO**: Provides real-time bidirectional event-based communication
- **Task Queue Management**: Maintains state of running and completed tasks
- **File System Integration**: Persists and retrieves task data from the filesystem

### 1.2 Core API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/generate-story` | POST | Initiates story generation with specified parameters |
| `/api/generate-report` | POST | Initiates report generation with optional search capabilities |
| `/api/status/<task_id>` | GET | Retrieves the current status of a generation task |
| `/api/result/<task_id>` | GET | Retrieves the final output text of a completed task |
| `/api/task-graph/<task_id>` | GET | Retrieves the hierarchical task graph for visualization |
| `/api/workspace/<task_id>` | GET | Retrieves the current article text (in-progress or final) |
| `/api/history` | GET | Lists all previous generation tasks |
| `/api/reload` | POST | Refreshes the server's task inventory from the filesystem |
| `/api/stop-task/<task_id>` | POST | Terminates a running generation task |
| `/api/delete-task/<task_id>` | DELETE | Removes a task and its associated files |
| `/api/ping` | GET | Health check endpoint |

### 1.3 WebSocket Events

The backend implements a real-time notification system using SocketIO with these key events:

| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Client→Server | Establishes WebSocket connection |
| `disconnect` | Client→Server | Terminates WebSocket connection |
| `subscribe_to_task` | Client→Server | Registers client for updates on a specific task |
| `subscription_status` | Server→Client | Confirms subscription status |
| `task_update` | Server→Client | Pushes real-time updates when task state changes |
| `connection_test` | Server→Client | Diagnostic event to verify connection health |

### 1.4 Task Execution Flow

When a new writing task is created:

1. The frontend sends a POST request to either `/api/generate-story` or `/api/generate-report`
2. The backend:
   - Creates a unique task ID
   - Establishes a directory structure for the task
   - Writes the prompt to a JSONL file
   - Creates a shell script to run the recursive engine
   - Launches the script as a subprocess
   - Sets up monitoring of task progress
   - Returns the task ID to the frontend

3. Task monitoring:
   - A background thread watches for changes to the `nodes.json` file
   - Changes are processed and broadcast to subscribed clients via WebSocket
   - The task status is updated in memory and on disk

4. When the task is complete:
   - The `done.txt` file is created by the engine
   - The task status is changed to "completed"
   - The final article text is extracted from `article.txt`

### 1.5 Task Graph Transformation

For visualization purposes, the backend transforms the engine's JSON graph structure into a hierarchical format better suited for frontend rendering:

```python
def transform_node_to_graph(node, seen_nodes=None, root=False):
    # Initialize seen_nodes if this is the root call
    if seen_nodes is None:
        seen_nodes = set()
    
    # Protect against cycles and duplicate nodes
    if node["hashkey"] in seen_nodes:
        return None
    seen_nodes.add(node["hashkey"])
    
    # Basic node information
    graph_node = {
        "id": node["nid"],
        "hashkey": node["hashkey"],
        "goal": node["task_info"]["goal"],
        "task_type": node["task_info"].get("task_type", ""),
        "status": node["status"],
        "is_execute_node": (node["node_type"] == "EXECUTE_NODE"),
        "result": node.get("result", {}).get("result", ""),
        "sub_tasks": []
    }
    
    # Recursively transform inner graph if exists
    if node.get("inner_graph") and node["inner_graph"].get("topological_task_queue"):
        collect_subtasks(node["inner_graph"]["topological_task_queue"], graph_node)
        
    return graph_node
```

This transformation creates a tree structure that:
- Maintains task hierarchies and dependencies
- Preserves execution state information
- Includes task results and metadata
- Flattens complex internal representation

## 2. Frontend Implementation

### 2.1 Architecture Overview

The WriteHERE frontend is built with React and Material-UI, providing a responsive and interactive user interface. The frontend architecture follows these key principles:

- **Component-Based Design**: UI elements are modularized as reusable components
- **Client-Side Routing**: Uses React Router for navigation between views
- **API Abstraction Layer**: Centralizes API calls in a dedicated utility module
- **Real-Time Updates**: Subscribes to WebSocket events for live progress updates
- **Responsive Design**: Adapts to different screen sizes and device types

### 2.2 Key Frontend Components

The frontend is organized into these primary components:

| Component | Purpose |
|-----------|---------|
| `App.js` | Root component and theme provider |
| `HomePage.js` | Landing page with task creation options |
| `StoryGenerationPage.js` | Interface for creating story generation tasks |
| `ReportGenerationPage.js` | Interface for creating report generation tasks |
| `ResultsPage.js` | Displays task progress, output, and visualization |
| `LiveTaskList.js` | Real-time visualization of task graph execution |
| `TaskGraph.js` | Interactive visualization of the task hierarchy |
| `HistoryPanel.js` | List of previously completed tasks |

### 2.3 State Management

The frontend maintains state at multiple levels:

#### 2.3.1 Component-Level State

Individual components use React's `useState` hooks to manage local state:

```javascript
// From ResultsPage.js
const [result, setResult] = useState(null);
const [loading, setLoading] = useState(true);
const [error, setError] = useState('');
const [taskList, setTaskList] = useState([]);
const [generationStatus, setGenerationStatus] = useState('generating');
const [progress, setProgress] = useState(0);
const [elapsedTime, setElapsedTime] = useState(0);
```

#### 2.3.2 URL-Based State

Task IDs are stored in the URL for persistence and sharing:

```javascript
// From ResultsPage.js
const { id } = useParams();
const location = useLocation();
const navigate = useNavigate();

// Generation details are passed through location state
const generationDetails = location.state || {
  prompt: 'Loading prompt...',
  model: 'Loading model...',
  type: 'unknown',
  status: 'unknown'
};
```

#### 2.3.3 Server-Synchronized State

Task execution state is synchronized with the backend through:
1. Regular polling of REST endpoints
2. Real-time WebSocket updates

```javascript
// Polling mechanism in ResultsPage.js
useEffect(() => {
  let pollInterval;
  
  const fetchStatus = async () => {
    try {
      const data = await getGenerationStatus(id);
      setGenerationStatus(data.status);
      setProgress(data.progress?.percent || 0);
      
      // If task is complete, fetch the result
      if (data.status === 'completed') {
        clearInterval(pollInterval);
        const resultData = await getGenerationResult(id);
        setResult(resultData);
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Poll every 2 seconds while task is running
  fetchStatus();
  pollInterval = setInterval(fetchStatus, 2000);
  
  return () => clearInterval(pollInterval);
}, [id]);
```

### 2.4 Real-Time Updates

Real-time updates are implemented using a Socket.IO client:

```javascript
// From LiveTaskList.js
useEffect(() => {
  // Initialize socket connection
  const socket = io(SOCKET_URL, {
    transports: ['polling', 'websocket'],
    reconnectionAttempts: 10,
    reconnectionDelay: 500,
    timeout: 10000
  });
  
  // Set up event handlers
  socket.on('connect', () => {
    setConnected(true);
    // Subscribe to updates for this task
    socket.emit('subscribe_to_task', { task_id: taskId });
  });
  
  socket.on('subscription_status', (data) => {
    if (data.status === 'subscribed' && data.task_id === taskId) {
      setSubscribed(true);
    }
  });
  
  socket.on('task_update', (data) => {
    if (data.task_id === taskId) {
      // Update local task graph state
      if (data.graph) {
        const processedTasks = flattenTasks(data.graph, [], true);
        setTasks(processedTasks);
      }
      
      // Check if task is complete
      if (data.status === 'completed') {
        setIsTaskComplete(true);
      }
    }
  });
  
  return () => {
    socket.disconnect();
  };
}, [taskId]);
```

This approach enables:
- Immediate updates as tasks are executed
- Real-time visualization of the writing process
- Reduced server load compared to continuous polling
- Better user experience with live progress feedback

### 2.5 Visualization Components

#### 2.5.1 Task List Visualization

The `LiveTaskList` component visualizes the task execution as a hierarchical list:

```jsx
{tasks.map((task) => (
  <ListItem
    key={task.hashkey}
    onClick={() => onTaskClick(task)}
    sx={{
      paddingLeft: `${(task.level * 24) + 16}px`,
      backgroundColor: task.selected ? 'rgba(25, 118, 210, 0.08)' : 'transparent',
      '&:hover': {
        backgroundColor: 'rgba(25, 118, 210, 0.04)'
      }
    }}
  >
    <ListItemIcon>
      {getTaskIcon(task.task_type)}
    </ListItemIcon>
    <ListItemText
      primary={task.goal}
      secondary={
        <>
          <Chip 
            size="small" 
            label={task.status} 
            color={getStatusColor(task.status)} 
          />
          {' '}
          <Chip 
            size="small" 
            label={task.task_type} 
            variant="outlined" 
          />
        </>
      }
    />
    <IconButton 
      onClick={(e) => toggleTaskExpansion(task.hashkey, e)}
    >
      {expandedTasks[task.hashkey] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
    </IconButton>
  </ListItem>
)}
```

This visualization:
- Displays task hierarchies with indentation
- Shows task status using color-coded chips
- Indicates task types with distinctive icons
- Allows expansion to view detailed information
- Highlights selected tasks for inspection

#### 2.5.2 Task Details View

When a task is selected, the system displays detailed information:

```jsx
{selectedTask && (
  <Paper elevation={3} sx={{ p: 2, mt: 2 }}>
    <Typography variant="h6">Task Details</Typography>
    <Typography variant="body2">
      <strong>Goal:</strong> {selectedTask.goal}
    </Typography>
    <Typography variant="body2">
      <strong>Type:</strong> {selectedTask.task_type}
    </Typography>
    <Typography variant="body2">
      <strong>Status:</strong> {selectedTask.status}
    </Typography>
    {selectedTask.result && (
      <>
        <Typography variant="subtitle1" sx={{ mt: 2 }}>Result:</Typography>
        <Box sx={{ 
          p: 2, 
          backgroundColor: 'grey.100', 
          borderRadius: 1, 
          maxHeight: '300px', 
          overflow: 'auto' 
        }}>
          <ReactMarkdown>{selectedTask.result}</ReactMarkdown>
        </Box>
      </>
    )}
  </Paper>
)}
```

This provides:
- Comprehensive details about the specific task
- The result/output of the task (if completed)
- Context for understanding the task's role in the overall writing process

## 3. API Interaction Patterns

### 3.1 Task Creation Flow

The frontend initiates task creation through these API calls:

```javascript
// From api.js
export const generateStory = async (params) => {
  try {
    const response = await apiClient.post('/generate-story', params);
    return response.data;
  } catch (error) {
    // Error handling...
  }
};

export const generateReport = async (params) => {
  try {
    const response = await apiClient.post('/generate-report', params);
    return response.data;
  } catch (error) {
    // Error handling...
  }
};
```

The parameters include:
- **prompt**: The writing task description
- **model**: The LLM to use (e.g., "gpt-4o", "claude-3-sonnet")
- **apiKeys**: API credentials for different services
- **enableSearch**: (Reports only) Whether to use search capabilities
- **searchEngine**: (Reports only) Which search backend to use

### 3.2 Task Monitoring Flow

Task monitoring follows this pattern:

1. Initial status fetch using REST API:
   ```javascript
   const data = await getGenerationStatus(taskId);
   ```

2. WebSocket subscription for real-time updates:
   ```javascript
   socket.emit('subscribe_to_task', { task_id: taskId });
   ```

3. Periodic polling as fallback:
   ```javascript
   pollInterval = setInterval(fetchStatus, 2000);
   ```

This multi-layered approach ensures reliable updates even if WebSocket connections fail.

### 3.3 Result Retrieval Flow

When tasks complete, results are retrieved through:

```javascript
const resultData = await getGenerationResult(taskId);
```

The result includes:
- The full generated text content
- Task metadata (model used, generation time, etc.)
- Links to additional resources

## 4. Frontend Control Features

### 4.1 Task Control Mechanisms

The frontend provides several control mechanisms for task management:

#### 4.1.1 Task Creation Controls

- **Input Form**: Captures prompt, model selection, and API keys
- **Search Toggle**: Enables/disables search capabilities for reports
- **Model Selection**: Chooses between different LLMs

#### 4.1.2 Runtime Controls

- **Stop Generation**: Can terminate a running task
```javascript
const handleStopGeneration = async () => {
  setStopInProgress(true);
  try {
    await stopTask(id);
    // Handle successful stop...
  } catch (error) {
    // Handle error...
  } finally {
    setStopInProgress(false);
    setStopConfirmOpen(false);
  }
};
```

- **Reload Task Status**: Forces refresh of task state
```javascript
await reloadTasks();
```

#### 4.1.3 Output Controls

- **Copy to Clipboard**: Copies generated text
- **Download**: Saves generated text as Markdown
- **View Task Graph**: Visualizes task execution structure

### 4.2 Error Handling

The frontend implements comprehensive error handling:

```javascript
try {
  // API call...
} catch (error) {
  if (error.response) {
    // Server returned an error response
    throw new Error(`Server error: ${error.response.data.error || error.response.statusText}`);
  } else if (error.request) {
    // No response received
    throw new Error('No response from server. Please check if the backend is running.');
  } else {
    // Other errors
    throw error;
  }
}
```

Error states are clearly displayed to users:

```jsx
{error && (
  <Alert severity="error" sx={{ mb: 2 }}>
    {error}
  </Alert>
)}
```

## 5. Data Visualization Techniques

### 5.1 Task Graph Visualization

The system visualizes the task graph in multiple ways:

#### 5.1.1 Hierarchical List

- Shows tasks with indentation to represent hierarchy
- Indicates dependencies through parent-child relationships
- Updates in real-time as tasks are executed
- Allows expansion/collapse of subtasks

#### 5.1.2 Status Indicators

- Color-coded status chips (green for complete, blue for in-progress, etc.)
- Icons for different task types (pen for writing, search icon for retrieval, etc.)
- Progress indicators for overall completion percentage

### 5.2 Article Visualization

The system provides real-time visualization of the developing article:

```jsx
<Box sx={{ mt: 3 }}>
  <Paper sx={{ p: 3 }}>
    <Typography variant="h5" gutterBottom>
      Generated Content
    </Typography>
    <Divider sx={{ mb: 2 }} />
    {result ? (
      <Box sx={{ whiteSpace: 'pre-wrap' }}>
        <ReactMarkdown>{result.content}</ReactMarkdown>
      </Box>
    ) : (
      <CircularProgress />
    )}
  </Paper>
</Box>
```

Key features:
- Markdown rendering for formatted output
- Live updates as content is generated
- Clear typography and spacing for readability

## 6. Performance Considerations

### 6.1 Backend Performance Optimizations

The backend implements several performance optimizations:

- **Subprocess Management**: Writing tasks run as separate processes to prevent blocking
- **Filesystem Monitoring**: Uses efficient file change detection instead of continuous polling
- **WebSocket Updates**: Pushes changes to clients rather than requiring polling
- **Caching**: Stores task information in memory for faster access
- **Load Protection**: Limits concurrent task execution

### 6.2 Frontend Performance Optimizations

The frontend implements these optimizations:

- **Memoization**: Uses React's `useMemo` and `useCallback` for expensive operations
- **Conditional Rendering**: Only renders components when necessary
- **Pagination**: Limits history display to avoid rendering large lists
- **Lazy Loading**: Defers loading of detailed task information until needed
- **Throttled Updates**: Limits frequency of WebSocket-triggered re-renders

## 7. Security Considerations

The API implementation includes several security measures:

- **API Key Isolation**: API keys are stored only for the current session and not persisted
- **Cross-Origin Protection**: CORS settings limit which domains can access the API
- **Input Validation**: All user inputs are validated before processing
- **Subprocess Sandboxing**: Execution is contained within specific directories
- **Resource Limits**: Timeouts prevent runaway processes

## 8. Conclusion

The WriteHERE system implements a sophisticated API architecture and frontend visualization that together enable:

1. **Real-time Monitoring**: Observing the writing process as it unfolds
2. **Interactive Control**: Managing task execution with granular control
3. **Hierarchical Visualization**: Understanding the structure of complex writing tasks
4. **Seamless Communication**: Bridging the core engine and user interface

This design provides unique insight into the recursive planning process that drives the system's writing capabilities, making the AI "thinking process" visible and allowing users to understand how complex writing tasks are broken down and solved step by step.

The combination of REST API endpoints for standard operations and WebSocket connections for real-time updates creates a responsive user experience that brings the recursive planning approach to life in the interface. 