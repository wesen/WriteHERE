import EventTable from './components/EventTable';
import './App.css';
import Container from 'react-bootstrap/Container';
import Tabs from 'react-bootstrap/Tabs';
import Tab from 'react-bootstrap/Tab';
import { GraphCanvas } from './components/GraphCanvas';

export default function App() {
  return (
    <Container fluid className="pt-4">
      <h1 className="text-center mb-4">Recursive Agent — Live Monitor</h1>
      <Tabs defaultActiveKey="events" id="main-tabs" className="mb-3">
        <Tab eventKey="events" title="Events">
          <EventTable />
        </Tab>
        <Tab eventKey="task-graph" title="Task Graph">
          <GraphCanvas />
        </Tab>
      </Tabs>
    </Container>
  );
}
