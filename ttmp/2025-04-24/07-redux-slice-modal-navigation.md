Below is a pattern that React teams (including the RTK/Bootstrap/Reaflow stack you already have) often use when they want *seamless, history-aware* navigation between several “floating” modals.  It builds directly on the primitives that already exist in your codebase—`NodeDetailModal`, `EventDetailModal`, and the helper callbacks such as `onNodeClick` and `renderClickableNodeId` you added earlier .

---

## 1.  Why a **modal-stack** kept in Redux is a good fit

* You are already using Redux Toolkit to hold global UI state for the graph and events.  
* Both `NodeDetailModal` and `EventDetailModal` are **presentational**; they don’t need to know *where* they were opened from, only *what* they should display.  
* You already pass `previousNodeId` into `NodeDetailModal` and show a back arrow —so a “stack” abstraction is almost there.

A Router-overlay approach (React-Router v6 “modal routes”) would also work, but you would first have to introduce routing everywhere (including inside the Electron build, if you have one).  Dropping a small slice into Redux is faster and keeps modals totally decoupled from the rest of the UI.

---

## 2.  The **`modalStack` slice**

```ts
// features/ui/modalStackSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface ModalDescriptor {
  type: 'node' | 'event';
  params: { nodeId?: string; eventId?: string };
}

interface ModalState {
  stack: ModalDescriptor[];
}

const initialState: ModalState = { stack: [] };

const modalStackSlice = createSlice({
  name: 'modalStack',
  initialState,
  reducers: {
    pushModal(state, action: PayloadAction<ModalDescriptor>) {
      state.stack.push(action.payload);
    },
    popModal(state) {
      state.stack.pop();
    },
    replaceTop(state, action: PayloadAction<ModalDescriptor>) {
      if (state.stack.length) state.stack[state.stack.length - 1] = action.payload;
      else state.stack.push(action.payload);
    },
  },
});

export const { pushModal, popModal, replaceTop } = modalStackSlice.actions;
export default modalStackSlice.reducer;
```

Add it to `store.ts` alongside your existing graph slice.

---

## 3.  A single **`ModalManager`** component

```tsx
// components/ModalManager.tsx
import NodeDetailModal from './NodeDetailModal';
import EventDetailModal from './EventDetailModal';
import { useAppSelector, useAppDispatch } from '../store';
import { popModal } from '../features/ui/modalStackSlice';

export const ModalManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const stack = useAppSelector(s => s.modalStack.stack);
  const top = stack[stack.length - 1];

  if (!top) return null;            // nothing to show

  const onHide = () => dispatch(popModal());

  switch (top.type) {
    case 'node':
      return (
        <NodeDetailModal
          show
          onHide={onHide}
          nodeId={top.params.nodeId!}
          onNodeClick={nodeId =>
            dispatch(pushModal({ type: 'node', params: { nodeId } }))
          }
          // go directly from node → event
          onEventClick={eventId =>
            dispatch(pushModal({ type: 'event', params: { eventId } }))
          }
        />
      );
    case 'event':
      return (
        <EventDetailModal
          show
          onHide={onHide}
          eventId={top.params.eventId!}
          // allow jumping to the related node
          onNodeClick={nodeId =>
            dispatch(pushModal({ type: 'node', params: { nodeId } }))
          }
        />
      );
    default:
      return null;
  }
};
```

Place `<ModalManager />` once at the root (e.g., just inside `App.tsx`) so it is always available.

---

## 4.  Wiring existing components into the stack

### 4.1 Event → modal

```tsx
// EventTable.tsx  (inside handleEventClick)
dispatch(pushModal({ type: 'event', params: { eventId: event.event_id } }));
```

### 4.2 Graph node → modal

```tsx
// GraphCanvas.tsx  (inside onNodeClick callback)
dispatch(pushModal({ type: 'node', params: { nodeId: id } }));
```

### 4.3 Inside **NodeDetailModal**

You already render each related event in a `ListGroup.Item` and call `setSelectedEvent(event)` .  
Swap that local state for:

```tsx
onClick={() =>
  dispatch(pushModal({ type: 'event', params: { eventId: event.event_id } }))
}
```

### 4.4 Inside **EventDetailModal**

Any place you render a node id (e.g., in `renderSummaryContent` for `node_created` events ):

```tsx
<Button variant="link" onClick={() => onNodeClick(event.payload.node_id!)}>
  {event.payload.node_id.slice(0, 8)}…
</Button>
```

`onNodeClick` is supplied by `ModalManager`.

---

## 5.  Back-stack behaviour “for free”

Because every modal *pushes* onto the slice, closing one (`popModal`) automatically reveals the previous.  The *Arrow-Left* you already show at the top of `NodeDetailModal` can therefore be simplified:

```tsx
<Button variant="link" onClick={() => dispatch(popModal())}>
  <ArrowLeft size={20} />
</Button>
```

No need to track `previousNodeId` any more—the store history is canonical.

---

## 6.  (Optional) **Sync with browser history**

If you want the browser Back button to pop the modal too:

```ts
// index.tsx
import { popModal } from './features/ui/modalStackSlice';

history.listen(({ action }) => {
  if (action === 'POP') store.dispatch(popModal());
});
```

---

## 7.  Benefits

* **Consistent API** — every UI element that wants a modal just dispatches `pushModal`.
* **Nested navigation** — users can drill Node → Event → Node indefinitely.
* **Predictable back** — always one modal per history entry.
* **No refactors** — both modals stay function components with minimal prop changes.

---

### TL;DR

Add a small Redux slice that stores an array of `{type, params}` objects and render only the *top* of that stack in a `ModalManager`. Dispatch `pushModal` whenever you want to open another modal (from rows, nodes, or links) and `popModal` when you want to go back.  Because your existing modals already expose `onNodeClick` / `onEventClick` hooks and show a **Back** arrow, most of the heavy lifting is done—this pattern simply formalises it and removes the ad-hoc `previousNodeId` plumbing.
