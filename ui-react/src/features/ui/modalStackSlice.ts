import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface ModalDescriptor {
  type: "node" | "event";
  params: { nodeId?: string; eventId?: string };
}

interface ModalState {
  stack: ModalDescriptor[];
}

const initialState: ModalState = { stack: [] };

const modalStackSlice = createSlice({
  name: "modalStack",
  initialState,
  reducers: {
    pushModal(state, action: PayloadAction<ModalDescriptor>) {
      state.stack.push(action.payload);
    },
    popModal(state) {
      state.stack.pop();
    },
    replaceTop(state, action: PayloadAction<ModalDescriptor>) {
      if (state.stack.length)
        state.stack[state.stack.length - 1] = action.payload;
      else state.stack.push(action.payload);
    },
    clearStack(state) {
      state.stack = [];
    },
  },
});

export const { pushModal, popModal, replaceTop, clearStack } =
  modalStackSlice.actions;
export default modalStackSlice.reducer;
