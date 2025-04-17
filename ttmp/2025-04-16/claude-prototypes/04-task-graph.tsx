import React, { useState, useEffect } from 'react';
import { Camera, Minimize2, Maximize2, ZoomIn, ZoomOut, RefreshCw, Filter } from 'lucide-react';

// Status color mapping from the specification
const STATUS_COLORS = {
  NOT_READY: '#9CA3AF', // Gray
  READY: '#3B82F6',     // Blue
  DOING: '#F59E0B',     // Yellow
  PLAN_DONE: '#10B981', // Green
  FINISH: '#10B981',    // Green
  FAILED: '#EF4444',    // Red
  NEED_UPDATE: '#8B5CF6', // Purple
  FINAL_TO_FINISH: '#6366F1', // Indigo
  NEED_POST_REFLECT: '#EC4899' // Pink
};

// Mock task node data
const MOCK_NODES = [
  {
    id: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff',
    status: 'READY',
    layer: 0,
    label: 'Collect data on current market demand',
    children: ['35e3cb86-530e-415f-bc20-13d03a47d1d2', 'a7f34d21-9bc5-4e1a-8b1d-46f8c2e9a312']
  },
  {
    id: '35e3cb86-530e-415f-bc20-13d03a47d1d2',
    status: 'PLAN_DONE',
    layer: 1,
    label: 'Write introduction and background section',
    children: ['c4d2a8f5-6e19-4c70-9f0a-b8e732d51b2c']
  },
  {
    id: 'a7f34d21-9bc5-4e1a-8b1d-46f8c2e9a312',
    status: 'DOING',
    layer: 1,
    label: 'Research current AI writing tools',
    children: []
  },
  {
    id: 'c4d2a8f5-6e19-4c70-9f0a-b8e732d51b2c',
    status: 'NOT_READY',
    layer: 2,
    label: 'Draft historical context section',
    children: []
  },
  {
    id: 'd9b7e3a1-5f28-4c0e-8d2a-e95f126c3a1b',
    status: 'FAILED',
    layer: 1,
    label: 'Analyze competitor features',
    children: []
  },
  {
    id: 'f8e1c2d3-4b5a-6d7e-8f9g-0h1i2j3k4l5m',
    status: 'FINISH',
    layer: 1,
    label: 'Define evaluation metrics',
    children: []
  }
];

// Mock connections between nodes
const MOCK_EDGES = [
  { source: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff', target: '35e3cb86-530e-415f-bc20-13d03a47d1d2' },
  { source: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff', target: 'a7f34d21-9bc5-4e1a-8b1d-46f8c2e9a312' },
  { source: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff', target: 'd9b7e3a1-5f28-4c0e-8d2a-e95f126c3a1b' },
  { source: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff', target: 'f8e1c2d3-4b5a-6d7e-8f9g-0h1i2j3k4l5m' },
  { source: '35e3cb86-530e-415f-bc20-13d03a47d1d2', target: 'c4d2a8f5-6e19-4c70-9f0a-b8e732d51b2c' },
];

// Component to render a node
const TaskNode = ({ node, isSelected, onClick }) => {
  const truncatedLabel = node.label.length > 25 ? node.label.substring(0, 22) + '...' : node.label;
  
  return (
    <div 
      className={`flex flex-col items-center cursor-pointer ${isSelected ? 'scale-110' : ''}`}
      onClick={() => onClick(node)}
    >
      <div 
        className="w-16 h-16 rounded-full flex items-center justify-center mb-2 transition-all duration-300"
        style={{ 
          backgroundColor: STATUS_COLORS[node.status],
          boxShadow: isSelected ? '0 0 0 3px rgba(59, 130, 246, 0.5)' : 'none'
        }}
      >
        <span className="text-white text-xs font-bold">ID-{node.id.substring(0, 4)}</span>
      </div>
      <div className="text-xs text-center max-w-32">{truncatedLabel}</div>
      <div className="text-xs text-gray-500">{node.status}</div>
    </div>
  );
};

// Component to render the task graph
const TaskGraphVisualization = () => {
  const [nodes, setNodes] = useState(MOCK_NODES);
  const [edges, setEdges] = useState(MOCK_EDGES);
  const [selectedNode, setSelectedNode] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isConnected, setIsConnected] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [statusFilter, setStatusFilter] = useState([]);

  useEffect(() => {
    // Simulate connecting to WebSocket
    const timer = setTimeout(() => {
      setIsConnected(true);
    }, 1500);
    
    return () => clearTimeout(timer);
  }, []);

  // Simulate receiving an event
  useEffect(() => {
    if (!isConnected) return;
    
    const interval = setInterval(() => {
      // Randomly update a node's status
      const statusOptions = ['NOT_READY', 'READY', 'DOING', 'PLAN_DONE', 'FINISH', 'FAILED'];
      const randomNodeIndex = Math.floor(Math.random() * nodes.length);
      const randomStatus = statusOptions[Math.floor(Math.random() * statusOptions.length)];
      
      setNodes(prevNodes => {
        const updatedNodes = [...prevNodes];
        updatedNodes[randomNodeIndex] = {
          ...updatedNodes[randomNodeIndex],
          status: randomStatus
        };
        return updatedNodes;
      });
    }, 5000);
    
    return () => clearInterval(interval);
  }, [isConnected, nodes]);

  const handleNodeClick = (node) => {
    setSelectedNode(node);
  };

  const handleZoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.1, 2));
  };

  const handleZoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.1, 0.5));
  };

  const handleResetZoom = () => {
    setZoomLevel(1);
  };

  const filteredNodes = statusFilter.length > 0 
    ? nodes.filter(node => statusFilter.includes(node.status))
    : nodes;

  const toggleStatusFilter = (status) => {
    setStatusFilter(prev => 
      prev.includes(status) 
        ? prev.filter(s => s !== status)
        : [...prev, status]
    );
  };

  // Group nodes by layer
  const nodesByLayer = {};
  filteredNodes.forEach(node => {
    if (!nodesByLayer[node.layer]) {
      nodesByLayer[node.layer] = [];
    }
    nodesByLayer[node.layer].push(node);
  });

  return (
    <div className="flex flex-col h-full w-full bg-gray-50 rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gray-800 text-white p-4 flex justify-between items-center">
        <h2 className="text-xl font-bold">WriteHERE Task Graph Visualization</h2>
        <div className="flex space-x-3">
          <button 
            className={`p-2 rounded ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} 
            title={isConnected ? 'Connected' : 'Disconnected'}
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </button>
          <button className="p-2 bg-blue-600 rounded" onClick={() => setShowFilters(!showFilters)}>
            <Filter size={18} />
          </button>
          <button className="p-2 bg-blue-600 rounded">
            <Camera size={18} />
          </button>
        </div>
      </div>
      
      {/* Filters panel */}
      {showFilters && (
        <div className="bg-white p-4 border-b">
          <h3 className="font-medium mb-2">Filter by Status</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(STATUS_COLORS).map(([status, color]) => (
              <button
                key={status}
                className="px-3 py-1 text-xs rounded-full flex items-center space-x-1"
                style={{ 
                  backgroundColor: statusFilter.includes(status) ? color : 'white',
                  color: statusFilter.includes(status) ? 'white' : 'black',
                  border: `1px solid ${color}`
                }}
                onClick={() => toggleStatusFilter(status)}
              >
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }}></span>
                <span>{status}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Graph visualization */}
        <div className="flex-1 relative overflow-auto p-4">
          <div className="absolute top-4 right-4 flex flex-col bg-white rounded shadow-md">
            <button className="p-2 hover:bg-gray-100" onClick={handleZoomIn}>
              <ZoomIn size={18} />
            </button>
            <button className="p-2 hover:bg-gray-100" onClick={handleZoomOut}>
              <ZoomOut size={18} />
            </button>
            <button className="p-2 hover:bg-gray-100" onClick={handleResetZoom}>
              <RefreshCw size={18} />
            </button>
          </div>
          
          <div
            className="min-h-full w-full flex flex-col items-start justify-start transition-transform duration-300"
            style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}
          >
            {/* Render each layer */}
            {Object.entries(nodesByLayer).sort((a, b) => a[0] - b[0]).map(([layer, layerNodes]) => (
              <div key={layer} className="w-full mb-16">
                <div className="bg-gray-200 px-3 py-1 mb-6 inline-block rounded">
                  <span className="text-sm font-medium">Layer {layer}</span>
                </div>
                <div className="flex justify-around">
                  {layerNodes.map(node => (
                    <TaskNode 
                      key={node.id} 
                      node={node} 
                      isSelected={selectedNode?.id === node.id}
                      onClick={handleNodeClick}
                    />
                  ))}
                </div>
              </div>
            ))}

            {/* SVG for edges (lines between nodes) */}
            <svg className="absolute top-0 left-0 w-full h-full pointer-events-none" style={{ zIndex: -1 }}>
              {edges.map((edge, index) => {
                const sourceNode = nodes.find(n => n.id === edge.source);
                const targetNode = nodes.find(n => n.id === edge.target);
                
                if (!sourceNode || !targetNode || 
                    (statusFilter.length > 0 && 
                     (!statusFilter.includes(sourceNode.status) || 
                      !statusFilter.includes(targetNode.status)))) {
                  return null;
                }
                
                // This is a simplified positioning - in a real app you'd calculate actual positions
                return (
                  <line 
                    key={index}
                    x1="50%"
                    y1={`${(sourceNode.layer * 16) + 8}%`}
                    x2="50%"
                    y2={`${(targetNode.layer * 16) + 8}%`}
                    stroke={selectedNode && (selectedNode.id === sourceNode.id || selectedNode.id === targetNode.id) 
                      ? "#3B82F6" 
                      : "#CBD5E1"}
                    strokeWidth={selectedNode && (selectedNode.id === sourceNode.id || selectedNode.id === targetNode.id) 
                      ? "2" 
                      : "1"}
                    strokeDasharray={targetNode.status === 'FAILED' ? "5,5" : ""}
                  />
                );
              })}
            </svg>
          </div>
        </div>
        
        {/* Details panel */}
        <div className="w-96 bg-white border-l overflow-y-auto p-4">
          <h3 className="font-bold text-lg mb-4">Node Details</h3>
          {selectedNode ? (
            <div>
              <div className="mb-4">
                <div className="flex items-center mb-2">
                  <div 
                    className="w-4 h-4 rounded-full mr-2" 
                    style={{ backgroundColor: STATUS_COLORS[selectedNode.status] }}
                  ></div>
                  <span className="font-semibold">{selectedNode.status}</span>
                </div>
                <h4 className="text-lg font-medium mb-1">{selectedNode.label}</h4>
                <p className="text-sm text-gray-500 mb-3">ID: {selectedNode.id}</p>
                <p className="text-sm text-gray-500 mb-3">Layer: {selectedNode.layer}</p>
              </div>
              
              <div className="mb-4">
                <h5 className="font-medium mb-2">Related Events</h5>
                <div className="space-y-2">
                  {/* Mock events for the selected node */}
                  <div className="p-3 bg-gray-50 rounded border text-sm">
                    <div className="flex justify-between mb-1">
                      <span className="font-medium text-blue-600">step_started</span>
                      <span className="text-gray-500">21:28:11</span>
                    </div>
                    <p className="text-gray-700">Step 16 started for node {selectedNode.id.substring(0, 8)}</p>
                  </div>
                  <div className="p-3 bg-gray-50 rounded border text-sm">
                    <div className="flex justify-between mb-1">
                      <span className="font-medium text-green-600">step_finished</span>
                      <span className="text-gray-500">21:28:12</span>
                    </div>
                    <p className="text-gray-700">Step completed with status: {selectedNode.status}</p>
                    <p className="text-gray-500 text-xs">Duration: 1017.089 seconds</p>
                  </div>
                  {selectedNode.status === 'PLAN_DONE' && (
                    <div className="p-3 bg-gray-50 rounded border text-sm">
                      <div className="flex justify-between mb-1">
                        <span className="font-medium text-yellow-500">llm_call_completed</span>
                        <span className="text-gray-500">21:28:11</span>
                      </div>
                      <p className="text-gray-700">Model: gpt-4o-mini</p>
                      <p className="text-gray-500 text-xs">Duration: 1017.006 seconds</p>
                    </div>
                  )}
                </div>
              </div>
              
              {selectedNode.children && selectedNode.children.length > 0 && (
                <div>
                  <h5 className="font-medium mb-2">Child Tasks</h5>
                  <ul className="space-y-2">
                    {selectedNode.children.map(childId => {
                      const childNode = nodes.find(n => n.id === childId);
                      return childNode ? (
                        <li 
                          key={childId} 
                          className="p-2 bg-gray-50 rounded border cursor-pointer hover:bg-gray-100"
                          onClick={() => setSelectedNode(childNode)}
                        >
                          <div className="flex items-center">
                            <div 
                              className="w-3 h-3 rounded-full mr-2" 
                              style={{ backgroundColor: STATUS_COLORS[childNode.status] }}
                            ></div>
                            <span>{childNode.label}</span>
                          </div>
                        </li>
                      ) : null;
                    })}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Select a node to view details</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default TaskGraphVisualization;