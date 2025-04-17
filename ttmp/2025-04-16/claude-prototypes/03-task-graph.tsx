import React, { useState, useEffect } from 'react';
import { Play, Pause, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react';

// Task status colors as defined in the documentation
const STATUS_COLORS = {
  'NOT_READY': '#9ca3af', // Gray
  'READY': '#3b82f6',     // Blue
  'DOING': '#f59e0b',     // Yellow
  'FINISH': '#10b981',    // Green
  'FAILED': '#ef4444',    // Red
  'PLAN_DONE': '#8b5cf6', // Purple
  'NEED_UPDATE': '#d97706', // Amber
  'FINAL_TO_FINISH': '#059669', // Emerald
  'NEED_POST_REFLECT': '#7c3aed' // Violet
};

// Sample data to represent the task graph
const initialNodes = [
  {
    id: 'e0968583-6e4e-4c6a-ab1e-97d74607d6ff',
    status: 'READY',
    label: 'Collect data on market demand',
    layer: 0,
    children: ['35e3cb86-530e-415f-bc20-13d03a47d1d2']
  },
  {
    id: '35e3cb86-530e-415f-bc20-13d03a47d1d2',
    status: 'PLAN_DONE',
    label: 'Write introduction and background',
    layer: 1,
    children: ['45a78c2d-92f7-4e8b-b543-890e3c7ab25f', '67d9a123-45c8-4fa9-b0cd-78e32e4591ab']
  },
  {
    id: '45a78c2d-92f7-4e8b-b543-890e3c7ab25f',
    status: 'DOING',
    label: 'Draft market analysis section',
    layer: 2,
    children: []
  },
  {
    id: '67d9a123-45c8-4fa9-b0cd-78e32e4591ab',
    status: 'NOT_READY',
    label: 'Draft AI tools overview section',
    layer: 2,
    children: []
  }
];

// Mock WebSocket event for simulation
const mockEvents = [
  {
    type: 'node_status_change',
    payload: {
      node_id: '45a78c2d-92f7-4e8b-b543-890e3c7ab25f',
      old: 'DOING',
      new: 'FINISH'
    },
    timestamp: '2025-04-16T21:29:15Z'
  },
  {
    type: 'node_status_change',
    payload: {
      node_id: '67d9a123-45c8-4fa9-b0cd-78e32e4591ab',
      old: 'NOT_READY',
      new: 'READY'
    },
    timestamp: '2025-04-16T21:29:25Z'
  },
  {
    type: 'node_status_change',
    payload: {
      node_id: '67d9a123-45c8-4fa9-b0cd-78e32e4591ab',
      old: 'READY',
      new: 'DOING'
    },
    timestamp: '2025-04-16T21:29:35Z'
  }
];

const TaskNode = ({ node, onClick }) => {
  return (
    <div 
      className="p-3 rounded-md shadow-md mb-2 cursor-pointer transition-all duration-300 hover:shadow-lg"
      style={{ backgroundColor: STATUS_COLORS[node.status] || '#9ca3af', borderLeft: '4px solid #1f2937' }}
      onClick={() => onClick(node)}
    >
      <div className="text-white font-medium truncate">{node.label}</div>
      <div className="text-white text-xs opacity-80 mt-1 flex justify-between">
        <span>{node.status}</span>
        <span>ID: {node.id.substring(0, 8)}...</span>
      </div>
    </div>
  );
};

const TaskGraphVisualization = () => {
  const [nodes, setNodes] = useState(initialNodes);
  const [selectedNode, setSelectedNode] = useState(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [eventIndex, setEventIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [connected, setConnected] = useState(false);

  // Simulate WebSocket connection
  useEffect(() => {
    const connectTimeout = setTimeout(() => {
      setConnected(true);
    }, 1500);

    return () => clearTimeout(connectTimeout);
  }, []);

  // Simulate receiving events from WebSocket
  useEffect(() => {
    if (!isPlaying || !connected || eventIndex >= mockEvents.length) return;

    const eventInterval = setInterval(() => {
      const event = mockEvents[eventIndex];
      
      if (event.type === 'node_status_change') {
        setNodes(prevNodes => 
          prevNodes.map(node => 
            node.id === event.payload.node_id 
              ? { ...node, status: event.payload.new } 
              : node
          )
        );
      }
      
      setEventIndex(prevIndex => prevIndex + 1);
      
      if (eventIndex >= mockEvents.length - 1) {
        setIsPlaying(false);
        clearInterval(eventInterval);
      }
    }, 3000);

    return () => clearInterval(eventInterval);
  }, [isPlaying, eventIndex, connected]);

  const handleNodeClick = (node) => {
    setSelectedNode(node);
  };

  const togglePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const resetSimulation = () => {
    setNodes(initialNodes);
    setEventIndex(0);
    setIsPlaying(true);
  };

  const handleZoomIn = () => {
    setZoom(prevZoom => Math.min(prevZoom + 0.1, 1.5));
  };

  const handleZoomOut = () => {
    setZoom(prevZoom => Math.max(prevZoom - 0.1, 0.7));
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-gray-800 text-white p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">WriteHERE Task Graph Visualization</h1>
        <div className="flex items-center space-x-2">
          <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span>{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* Connection status banner */}
      {!connected && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4" role="alert">
          <p className="font-bold">Disconnected</p>
          <p>No connection to event stream. Reconnecting...</p>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Task Graph */}
        <div className="w-3/4 p-4 overflow-auto">
          <div className="mb-4 flex justify-between items-center">
            <h2 className="text-lg font-semibold">Task Hierarchy</h2>
            <div className="flex space-x-2">
              <button 
                className="p-2 bg-gray-200 rounded hover:bg-gray-300"
                onClick={togglePlayPause}
              >
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <button 
                className="p-2 bg-gray-200 rounded hover:bg-gray-300"
                onClick={handleZoomIn}
              >
                <ZoomIn size={16} />
              </button>
              <button 
                className="p-2 bg-gray-200 rounded hover:bg-gray-300"
                onClick={handleZoomOut}
              >
                <ZoomOut size={16} />
              </button>
              <button 
                className="p-2 bg-gray-200 rounded hover:bg-gray-300"
                onClick={resetSimulation}
              >
                <RefreshCw size={16} />
              </button>
            </div>
          </div>

          <div 
            className="flex transition-transform"
            style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
          >
            {/* Task layers */}
            {[0, 1, 2].map(layer => (
              <div key={layer} className="w-64 mx-2">
                <div className="bg-gray-700 text-white p-2 rounded-t-md mb-2">
                  Layer {layer}
                </div>
                {nodes
                  .filter(node => node.layer === layer)
                  .map(node => (
                    <TaskNode 
                      key={node.id} 
                      node={node} 
                      onClick={handleNodeClick} 
                    />
                  ))
                }
              </div>
            ))}
          </div>

          {/* Task connections visualization - simplified with lines */}
          <svg 
            className="absolute top-0 left-0 w-full h-full pointer-events-none"
            style={{ zIndex: -1 }}
          >
            {nodes.map(node => (
              node.children.map(childId => {
                const childNode = nodes.find(n => n.id === childId);
                if (!childNode) return null;
                
                // This is a simplified approach - in a real implementation you would
                // calculate actual positions based on DOM elements
                return (
                  <line 
                    key={`${node.id}-${childId}`}
                    x1={100 + node.layer * 280} 
                    y1={180 + nodes.indexOf(node) * 100}
                    x2={100 + childNode.layer * 280} 
                    y2={180 + nodes.indexOf(childNode) * 100}
                    stroke="#9ca3af"
                    strokeWidth="2"
                    strokeDasharray="5,5"
                  />
                );
              })
            ))}
          </svg>
        </div>

        {/* Details Panel */}
        <div className="w-1/4 bg-white p-4 border-l border-gray-200 overflow-y-auto">
          <h2 className="text-lg font-semibold mb-4">Node Details</h2>
          
          {selectedNode ? (
            <div>
              <div className="mb-2">
                <span className="font-medium">ID:</span> {selectedNode.id}
              </div>
              <div className="mb-2">
                <span className="font-medium">Label:</span> {selectedNode.label}
              </div>
              <div className="mb-2">
                <span className="font-medium">Status:</span> 
                <span 
                  className="ml-2 px-2 py-1 rounded text-white text-sm"
                  style={{ backgroundColor: STATUS_COLORS[selectedNode.status] }}
                >
                  {selectedNode.status}
                </span>
              </div>
              <div className="mb-2">
                <span className="font-medium">Layer:</span> {selectedNode.layer}
              </div>
              <div className="mb-2">
                <span className="font-medium">Children:</span> 
                <ul className="mt-1 ml-4 list-disc">
                  {selectedNode.children.length > 0 ? (
                    selectedNode.children.map(childId => {
                      const childNode = nodes.find(node => node.id === childId);
                      return (
                        <li key={childId} className="mb-1">
                          {childNode ? childNode.label : childId}
                        </li>
                      );
                    })
                  ) : (
                    <li className="text-gray-500">No children</li>
                  )}
                </ul>
              </div>
            </div>
          ) : (
            <div className="text-gray-500">
              Select a node to view details
            </div>
          )}
        </div>
      </div>

      {/* Status Bar */}
      <div className="bg-gray-200 p-2 flex justify-between text-sm border-t border-gray-300">
        <div>
          Nodes: {nodes.length} | Events processed: {eventIndex}/{mockEvents.length}
        </div>
        <div>
          Status: {isPlaying ? 'Simulating' : 'Paused'} | Zoom: {Math.round(zoom * 100)}%
        </div>
      </div>
    </div>
  );
};

export default TaskGraphVisualization;