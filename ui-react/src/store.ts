import { configureStore } from "@reduxjs/toolkit";
import { eventsApi } from "./features/events/eventsApi";
import graphReducer from "./features/graph/graphSlice";
import modalStackReducer from "./features/ui/modalStackSlice";
import { useDispatch, useSelector } from "react-redux";
import { TypedUseSelectorHook } from "react-redux";

export const store = configureStore({
  reducer: {
    [eventsApi.reducerPath]: eventsApi.reducer,
    graph: graphReducer,
    modalStack: modalStackReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(eventsApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

// Hooks for easier typing
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
