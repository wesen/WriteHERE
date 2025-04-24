WARMUP :

- [ ] Refactor the styling of events in ui-react since a lot of html / styling
      is duplicated (for example eventTypeBadgeVariant or eventTypeConfig)

## BUGS / issues

- [x] Weird issues where a task gets cancelled and no redis events are received
- [.] SOurcemaps in vite don't get loade (not fixing for now)

- [ ] Add run_id to the run started event
- [ ] Add run_id to the events themselves

- [ ] Some nodes don't seem to have parents
- [ ] What about N/A status of new nodes?
- [ ] Add run_id to the run started event
- [ ] First node never has a node_added event

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

## UI stuff

- [x] Show more of the metadata fields now that context has been extended
- [x] Clicking on a node shows all the events associated with that node
- [ ] Potentially also more state information about the results

- [ ] Make the graph scrollable + filterable
- [ ] Click on a node ID in the event log and get info about the node + able to visualize it in the graph (similarly, events in graph click back to event log)
- [ ] Sidebar with events in the graph view?

## BIG feature

- [x] Build up a node visualization of the task graph on the frontend

  - [x] Use redux to process incoming (graph) events

- [x] Collect the node events to server a built up graph on the backend

- [ ] Record LLM calls to replay to avoid hitting the API

- [ ] Record all events to sqlite to analyze later

- [ ] Restore recursive state from sqlite

## Future

- [ ] Restart nodes and tasks in recursive (restore agent state basically)
