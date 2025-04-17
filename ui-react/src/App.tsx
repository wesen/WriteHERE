import EventTable from './components/EventTable';
import './App.css';
import Container from 'react-bootstrap/Container';

function App() {
  return (
    <Container fluid>
      <h1 className="text-center my-4">Recursive Agent - Live Event Stream (React)</h1>
      <EventTable />
    </Container>
  );
}

export default App;
