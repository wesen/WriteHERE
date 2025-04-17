import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle, CheckCircle, Clock, ArrowRight, Play, XCircle, Filter, Zap, Database, Search } from 'lucide-react';

// Mock data for demonstration
const mockEvents = [
  {
    id: '1',
    ts: new Date().toISOString(),
    type: 'STEP_STARTED',
    payload: {
      step: 16,
      node_id: '35e3cb86-530e-415f-bc20-13d03a47d1d2',
      node_goal: 'Write the introduction and background section of the report, defining long-article writing AI agents, discussing the importance of content creation in the digital age, and stating the purpose of the report, in approximately 500 words.',
      root_id: 'abfbe884-12d6-45e4-897e-8f292e607e65'
    }
  },
  {
    id: '2',
    ts: new Date().toISOString(),
    type: 'STEP_FINISHED',
    payload: {
      node_id: '35e3cb86-530e-415f-bc20-13d03a47d1d2',
      action_name: 'plan',
      status_after: 'PLAN_DONE',
      duration_seconds: 1017.0892921049963
    }
  },
  {
    id: '3',
    ts: new Date().toISOString(),
    type: 'NODE_STATUS_CHANGE',
    payload: {
      node_id: '35e3cb86-530e-415f-bc20-13d03a47d1d2',
      old_status: 'NOT_READY',
      new_status: 'READY'
    }
  },
  {
    id: '4',
    ts: new Date().toISOString(),
    type: 'LLM_CALL_COMPLETED',
    payload: {
      agent_class: 'UpdateAtomPlanningAgent',
      model: 'gpt-4o-mini',
      duration_seconds: 1017.0066934790229,
      result_summary: "<think>The goal of the writing task is to \"Write the introduction and background section of the report, defining long-article writing AI agents, discussing the importance of content creation in the digital age, and stating the purpose of the report, in approximately 500 words.\"</think>"
    }
  },
  {
    id: '5',
    ts: new Date().toISOString(),
    type: 'TOOL_INVOKED',
    payload: {
      tool_name: 'web_search',
      api_name: 'google_search',
      args_hash: 'a1b2c3',
      query: 'current market demand for AI writing tools statistics 2025'
    }
  }
];

// Event type to icon/color mapping
const eventTypeConfig = {
  STEP_STARTED: { icon: Play, color: 'text-blue-500', bgColor: 'bg-blue-100' },
  STEP_FINISHED: { icon: CheckCircle, color: 'text-green-500', bgColor: 'bg-green-100' },
  NODE_STATUS_CHANGE: { icon: ArrowRight, color: 'text-purple-500', bgColor: 'bg-purple-100' },
  LLM_CALL_STARTED: { icon: Clock, color: 'text-yellow-500', bgColor: 'bg-yellow-100' },
  LLM_CALL_COMPLETED: { icon: Zap, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  TOOL_INVOKED: { icon: Database, color: 'text-indigo-500', bgColor: 'bg-indigo-100' },
  TOOL_RETURNED: { icon: Database, color: 'text-indigo-700', bgColor: 'bg-indigo-100' },
  SEARCH_COMPLETED: { icon: Search, color: 'text-blue-700', bgColor: 'bg-blue-100' }
};

// Status color mapping
const statusColorMap = {
  NOT_READY: 'text-gray-500',
  READY: 'text-blue-500',
  DOING: 'text-yellow-500',
  FINISH: 'text-green-500',
  FAILED: 'text-red-500',
  PLAN_DONE: 'text-teal-500',
  NEED_UPDATE: 'text-orange-500',
  FINAL_TO_FINISH: 'text-emerald-500',
  NEED_POST_REFLECT: 'text-indigo-500'
};

// Main App Component
const WriteHEREVisualizer = () => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [events, setEvents] = useState(mockEvents);
  const [activeTab, setActiveTab] = useState('events');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [activeFilters, setActiveFilters] = useState([]);
  const [taskGraph, setTaskGraph] = useState({});
  
  // Simulating WebSocket connection
  useEffect(() => {
    // In a real app, you would connect to the WebSocket here
    const timer = setTimeout(() => {
      setConnectionStatus('connected');
    }, 2000);
    
    return () => clearTimeout(timer);
  }, []);

  // Filter events based on active filters
  const filteredEvents = activeFilters.length > 0 
    ? events.filter(event => activeFilters.includes(event.type))
    : events;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gray-800 text-white p-4">
        <div className="flex justify-between items-center">
          <h1 className="text-xl font-bold">WriteHERE Event Visualization Dashboard</h1>
          <div className="flex items-center space-x-2">
            <div className={`px-3 py-1 rounded-full ${connectionStatus === 'connected' ? 'bg-green-500' : 'bg-red-500'}`}>
              {connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </div>
      </header>
      
      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-4 px-4">
          <button 
            className={`py-3 px-4 ${activeTab === 'events' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
            onClick={() => setActiveTab('events')}
          >
            Event Stream
          </button>
          <button 
            className={`py-3 px-4 ${activeTab === 'graph' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
            onClick={() => setActiveTab('graph')}
          >
            Task Graph
          </button>
          <button 
            className={`py-3 px-4 ${activeTab === 'timeline' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
            onClick={() => setActiveTab('timeline')}
          >
            Timeline
          </button>
          <button 
            className={`py-3 px-4 ${activeTab === 'llm' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
            onClick={() => setActiveTab('llm')}
          >
            LLM Monitor
          </button>
          <button 
            className={`py-3 px-4 ${activeTab === 'document' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
            onClick={() => setActiveTab('document')}
          >
            Document View
          </button>
        </nav>
      </div>
      
      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex">
        {activeTab === 'events' && (
          <div className="flex-1 flex flex-col h-full">
            {/* Filters */}
            <div className="p-4 bg-white border-b">
              <div className="flex items-center space-x-2">
                <Filter size={18} className="text-gray-500" />
                <span className="font-medium">Filter by type:</span>
                {Object.keys(eventTypeConfig).map(type => (
                  <button
                    key={type}
                    className={`px-3 py-1 rounded-full text-xs ${activeFilters.includes(type) 
                      ? `${eventTypeConfig[type].bgColor} ${eventTypeConfig[type].color}`
                      : 'bg-gray-100 text-gray-600'}`}
                    onClick={() => {
                      if (activeFilters.includes(type)) {
                        setActiveFilters(activeFilters.filter(t => t !== type));
                      } else {
                        setActiveFilters([...activeFilters, type]);
                      }
                    }}
                  >
                    {type.toLowerCase().replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Event Table */}
            <div className="flex-1 overflow-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Run ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Payload / Details</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredEvents.map((event, index) => (
                    <tr 
                      key={event.id} 
                      className={`${selectedEvent?.id === event.id ? 'bg-blue-50' : ''} hover:bg-gray-50 cursor-pointer`}
                      onClick={() => setSelectedEvent(event)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(event.ts).toLocaleTimeString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${eventTypeConfig[event.type]?.bgColor} ${eventTypeConfig[event.type]?.color}`}>
                          {React.createElement(eventTypeConfig[event.type]?.icon, { size: 12, className: 'mr-1' })}
                          {event.type.toLowerCase().replace(/_/g, ' ')}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {event.payload.root_id?.substr(0, 8) || 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 max-w-lg truncate">
                        {event.type === 'NODE_STATUS_CHANGE' && (
                          <div className="flex items-center">
                            <span className={statusColorMap[event.payload.old_status]}>{event.payload.old_status}</span>
                            <ArrowRight size={14} className="mx-2" />
                            <span className={statusColorMap[event.payload.new_status]}>{event.payload.new_status}</span>
                          </div>
                        )}
                        {event.type === 'STEP_STARTED' && (
                          <div className="truncate">{event.payload.node_goal?.substr(0, 100)}{event.payload.node_goal?.length > 100 ? '...' : ''}</div>
                        )}
                        {event.type === 'STEP_FINISHED' && (
                          <div>
                            Action: <span className="font-medium">{event.payload.action_name}</span>, 
                            Status: <span className={statusColorMap[event.payload.status_after]}>{event.payload.status_after}</span>,
                            Duration: <span className="font-medium">{event.payload.duration_seconds?.toFixed(2)}s</span>
                          </div>
                        )}
                        {event.type === 'LLM_CALL_COMPLETED' && (
                          <div className="truncate">
                            Model: <span className="font-medium">{event.payload.model}</span>,
                            Agent: <span className="font-medium">{event.payload.agent_class}</span>,
                            Duration: <span className="font-medium">{event.payload.duration_seconds?.toFixed(2)}s</span>
                          </div>
                        )}
                        {event.type === 'TOOL_INVOKED' && (
                          <div className="truncate">
                            Tool: <span className="font-medium">{event.payload.tool_name}</span>,
                            API: <span className="font-medium">{event.payload.api_name}</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {activeTab === 'graph' && (
          <div className="flex-1 p-6 bg-white">
            <h2 className="text-xl font-semibold mb-4">Task Graph Visualization</h2>
            <div className="bg-gray-100 rounded-lg p-12 flex items-center justify-center h-4/5">
              <div className="text-center text-gray-500">
                <p className="mb-2">Interactive Task Graph would be displayed here</p>
                <p className="text-sm">Showing parent-child relationships and task dependencies</p>
              </div>
            </div>
          </div>
        )}
        
        {activeTab === 'timeline' && (
          <div className="flex-1 p-6 bg-white">
            <h2 className="text-xl font-semibold mb-4">Event Timeline</h2>
            <div className="bg-gray-100 rounded-lg p-12 flex items-center justify-center h-4/5">
              <div className="text-center text-gray-500">
                <p className="mb-2">Chronological Event Timeline would be displayed here</p>
                <p className="text-sm">With the ability to zoom, pan, and filter events</p>
              </div>
            </div>
          </div>
        )}
        
        {activeTab === 'llm' && (
          <div className="flex-1 p-6 bg-white">
            <h2 className="text-xl font-semibold mb-4">LLM Monitoring Dashboard</h2>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Total Calls</h3>
                <p className="text-3xl font-bold">24</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Avg Response Time</h3>
                <p className="text-3xl font-bold">1.42s</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Total Tokens</h3>
                <p className="text-3xl font-bold">15,240</p>
              </div>
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Estimated Cost</h3>
                <p className="text-3xl font-bold">$0.31</p>
              </div>
            </div>
            <div className="bg-gray-100 rounded-lg p-12 flex items-center justify-center h-3/5">
              <div className="text-center text-gray-500">
                <p className="mb-2">LLM Usage Charts would be displayed here</p>
                <p className="text-sm">Including call frequency, token usage, and model distribution</p>
              </div>
            </div>
          </div>
        )}
        
        {activeTab === 'document' && (
          <div className="flex-1 p-6 bg-white">
            <h2 className="text-xl font-semibold mb-4">Document Composition View</h2>
            <div className="bg-gray-100 rounded-lg p-12 flex items-center justify-center h-4/5">
              <div className="text-center text-gray-500">
                <p className="mb-2">Document Assembly Visualization would be displayed here</p>
                <p className="text-sm">Showing how the final document is built from component parts</p>
              </div>
            </div>
          </div>
        )}
        
        {/* Event Details Panel */}
        {selectedEvent && (
          <div className="w-1/3 border-l border-gray-200 bg-white overflow-auto">
            <div className="p-4 border-b border-gray-200 flex justify-between items-center">
              <h3 className="text-lg font-medium">Event Details</h3>
              <button 
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setSelectedEvent(null)}
              >
                <XCircle size={20} />
              </button>
            </div>
            <div className="p-4">
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-500 mb-1">Event Type</h4>
                <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-sm font-medium ${eventTypeConfig[selectedEvent.type]?.bgColor} ${eventTypeConfig[selectedEvent.type]?.color}`}>
                  {React.createElement(eventTypeConfig[selectedEvent.type]?.icon, { size: 16, className: 'mr-1' })}
                  {selectedEvent.type}
                </div>
              </div>
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-500 mb-1">Timestamp</h4>
                <p className="text-sm">{new Date(selectedEvent.ts).toLocaleString()}</p>
              </div>
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-500 mb-1">Event ID</h4>
                <p className="text-sm font-mono">{selectedEvent.id}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-1">Payload</h4>
                <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto max-h-96">
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WriteHEREVisualizer;