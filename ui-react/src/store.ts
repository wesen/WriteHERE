import { configureStore } from "@reduxjs/toolkit";
import { eventsApi } from "./features/events/eventsApi";
import graphReducer from "./features/graph/graphSlice";

export const store = configureStore({
  reducer: {
    [eventsApi.reducerPath]: eventsApi.reducer,
    graph: graphReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(eventsApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
