- [x] propagate step number to the llm calls
  - [ ] propagate step number in node status changed events too
- [x] see full prompt and prompt response

## Event changes

- [ ] add prompt to llm_step_completed

## New Events

- [ ] add a program start event
- [x] events for node creation
- [ ] add node type / status to execution context
- [ ] add current graph to graph modification events
- [ ] link plan received and other downstream from an llm call events with the llm event info

## UI improvements

- [x] Render the prompt preview in a nicer fashion
- [ ] Render as markdown
- [ ] Add filters to only show certain types of events (for example, hide node added / edge added)
- [ ] render graphs of the graph being built

- [x] modal with info
- [ ] show related steps
- [ ] show step type + status next to step events ( as a column)

- [ ] redux actions for incoming events
- [ ] reducing events on the server side to serve a full events log on REST API
- [ ] reducing the graph on the frontend and the backend

- [ ] running times for tasks

- [ ] in events that are linked to a node, always show node type / node status at the time of the event

## Future Features

- [ ] actions to interact with the backend

## Janitorial

- [ ] storybook

---

- [x] remove fallback handling in abstract.py
