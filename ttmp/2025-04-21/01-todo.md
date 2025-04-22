## BUGS / issues

- [ ] Some nodes don't seem to have parents
- [ ] What about N/A status of new nodes?

## Ideas for events

- [ ] add events when nodes are computed / scheduled / created in engine.py (forward_one_step_not_parallel)
- [ ] add run started event
- [ ] Add lllm call id to link completed to started + tool calls to parent

## UI stuff

- [ ] Show more of the metadata fields now that context has been extended
- [ ] Clicking on a node shows all the events associated with that node
- [ ] Potentially also more state information about the results

- [ ] Make the graph scrollable + filterable
- [ ] Click on a node ID in the event log and get info about the node + able to visualize it in the graph (similarly, events in graph click back to event log)
- [ ] Sidebar with events in the graph view?

## BIG feature

- [x] Build up a node visualization of the task graph on the frontend

  - [x] Use redux to process incoming (graph) events

- [ ] Collect the node events to server a built up graph on the backend

## Future

- [ ] Restart nodes and tasks

## TODO menial

- [x] pass execution context to emit_llm_call_started/completed
- [ ] pass execution context to tool_calls
