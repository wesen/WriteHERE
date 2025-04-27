import { useEffect } from 'react';
import EventTable from './components/EventTable';
import './App.css';
import Container from 'react-bootstrap/Container';
import Tabs from 'react-bootstrap/Tabs';
import Tab from 'react-bootstrap/Tab';
import { GraphCanvas } from './components/GraphCanvas';
import { useDispatch } from 'react-redux';
import { initializeGraphState } from './features/graph/graphSlice';
import { AppDispatch } from './store';
import ModalManager from './components/ModalManager';
import Dashboard from './components/Dashboard';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  const dispatch = useDispatch<AppDispatch>();

  // Initialize graph state when the application loads
  useEffect(() => {
    dispatch(initializeGraphState());
  }, [dispatch]);

  return (
    <Container fluid className="pt-4">
      <h1 className="text-center mb-4">Recursive Agent — Live Monitor</h1>
      <Tabs defaultActiveKey="dashboard" id="main-tabs" className="mb-3">
        <Tab eventKey="dashboard" title="Dashboard">
          <ErrorBoundary>
            <Dashboard />
          </ErrorBoundary>
        </Tab>
        <Tab eventKey="events" title="Events">
          <ErrorBoundary>
            <EventTable />
          </ErrorBoundary>
        </Tab>
        <Tab eventKey="task-graph" title="Task Graph">
          <ErrorBoundary>
            <GraphCanvas />
          </ErrorBoundary>
        </Tab>
      </Tabs>
      
      {/* Modal Manager handles all modal display and navigation */}
      <ModalManager />
    </Container>
  );
}
