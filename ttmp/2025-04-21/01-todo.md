## UI stuff

- [x] Show more of the metadata fields now that context has been extended
- [x] Clicking on a node shows all the events associated with that node
- [ ] Potentially also more state information about the results

- [ ] Make the graph scrollable + filterable
- [ ] Add a "go to node / go to event" button in the modals to switch views / scroll to the relevant place .
- [ ] Add a previous / after navigation to the event modal
- [ ] Autoscroll toggle in the event view.

- [ ] Related events in the graph node modal should show the detail snippet

- [ ] Refactor the styling of events in ui-react since a lot of html / styling
      is duplicated (for example eventTypeBadgeVariant or eventTypeConfig)

  - [ ] Fix white font in the node detail modal
  - [ ] show the NID in the events list

- [ ] Implement details view for node result available

- [ ] show the metadata of the node_created event when clicking on the node

- [x] outer node id should be reflected in the graph as a parent relation ship maybe?

- [ ] Add a way to test some preset graphs / browse through runs
- [ ] Make the outer/inner relationship actually readable
- [ ] Zoom in /filter on a subpart (inner nodes) of the graph / children nodes

- [ ] Make the graph canvas resize so it contains the full thing
- [ ] Make it pannable with the mou

- [ ] Little dashboard with currently executing steps and tool calls with little spinners or so

## Research

- [ ] CLone reaflow and write proper documentation

## BUGS / issues

- [ ] Restore inner_nodes on initial graph load

- [x] Weird issues where a task gets cancelled and no redis events are received
- [.] SOurcemaps in vite don't get loade (not fixing for now)

- [x] Add run_id to the run started event
- [x] Add run_id to the events themselves

- [ ] Some nodes don't seem to have parents
- [ ] What about N/A status of new nodes?
- [x] Add run_id to the run started event
- [x] First node never has a node_added event
- [ ] edge_added is missing the step number

## TODO menial

- [x] pass execution context to emit_llm_call_started/completed
- [ ] Batch node creation and edge creation
- [ ] Extract some common payload types for the eventsApi.ts

## Ideas for events

- [ ] add events when nodes are computed / scheduled / created in engine.py (forward_one_step_not_parallel)
- [ ] add events when templates are rendered or parsed
- [x] add run started event
- [ ] Add llm call id to link completed to started + tool calls to parent
- [ ] pass execution context to tool_calls
- [ ] What is Layer number?

## BIG feature

- [x] Build up a node visualization of the task graph on the frontend

  - [x] Use redux to process incoming (graph) events

- [x] Collect the node events to server a built up graph on the backend

- [x] Record LLM calls to replay to avoid hitting the API

- [x] Record all events to sqlite to analyze later

## Future

- [ ] Restart nodes and tasks in recursive (restore agent state basically)
