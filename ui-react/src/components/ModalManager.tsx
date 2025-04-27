import React, { useEffect, useMemo } from 'react';
import NodeDetailModal from './NodeDetailModal';
import EventDetailModal from './EventDetailModal';
import { useAppSelector, useAppDispatch } from '../store';
import { pushModal, popModal, clearStack, replaceTop } from '../features/ui/modalStackSlice';
import { useGetEventsQuery } from '../features/events/eventsApi';

export const ModalManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const stack = useAppSelector(s => s.modalStack.stack);
  const top = stack[stack.length - 1];
  const { data: eventsData } = useGetEventsQuery();

  // Get sorted events by timestamp for navigation
  const sortedEvents = useMemo(() => {
    if (!eventsData?.events) return [];
    // Create a copy and sort by timestamp (oldest to newest)
    return [...eventsData.events].sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [eventsData]);

  // Handle browser back button for modal navigation
  useEffect(() => {
    const handlePopState = () => {
      if (stack.length > 0) {
        dispatch(popModal());
      }
    };
    
    window.addEventListener('popstate', handlePopState);
    
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [dispatch, stack.length]);

  // Push state to history when a modal is added
  useEffect(() => {
    if (stack.length > 0) {
      window.history.pushState({ modalStack: true }, '');
    }
  }, [stack.length]);

  if (!top) return null; // nothing to show

  const onHide = () => {
    // When explicitly closing the modal, clear the entire stack
    dispatch(clearStack());
    // Also clear browser history states we've added
    const historyDepth = stack.length;
    for (let i = 0; i < historyDepth; i++) {
      window.history.back();
    }
  };

  const onBack = () => dispatch(popModal());

  const onNodeClick = (nodeId: string) => {
    dispatch(pushModal({ type: 'node', params: { nodeId } }));
  };

  const onEventClick = (eventId: string) => {
    dispatch(pushModal({ type: 'event', params: { eventId } }));
  };

  const findAdjacentEvent = (currentEventId: string, direction: 'prev' | 'next') => {
    if (!sortedEvents.length) return null;
    
    // Find the current event's index in the sorted array
    const currentIndex = sortedEvents.findIndex(e => e.event_id === currentEventId);
    if (currentIndex === -1) return null;
    
    // Find the adjacent event based on direction
    const adjacentIndex = direction === 'prev' ? currentIndex - 1 : currentIndex + 1;
    
    // Check if the adjacent index is valid
    if (adjacentIndex < 0 || adjacentIndex >= sortedEvents.length) return null;
    
    return sortedEvents[adjacentIndex];
  };

  const navigateToEvent = (eventId: string) => {
    dispatch(replaceTop({ type: 'event', params: { eventId } }));
  };

  switch (top.type) {
    case 'node':
      return (
        <NodeDetailModal
          show
          onHide={onHide}
          nodeId={top.params.nodeId!}
          onNodeClick={onNodeClick}
          onEventClick={onEventClick}
          hasPrevious={stack.length > 1}
          onBack={onBack}
        />
      );
    case 'event':
      // Find the event by its ID
      const event = eventsData?.events.find(e => e.event_id === top.params.eventId);
      if (!event) return null;
      
      // Find previous and next events
      const previousEvent = findAdjacentEvent(event.event_id, 'prev');
      const nextEvent = findAdjacentEvent(event.event_id, 'next');
      
      const onPrevious = () => {
        if (previousEvent) {
          navigateToEvent(previousEvent.event_id);
        }
      };
      
      const onNext = () => {
        if (nextEvent) {
          navigateToEvent(nextEvent.event_id);
        }
      };
      
      return (
        <EventDetailModal
          show
          onHide={onHide}
          event={event}
          onNodeClick={onNodeClick}
          hasPrevious={stack.length > 1}
          onBack={onBack}
          onPrevious={onPrevious}
          onNext={onNext}
          hasPreviousEvent={!!previousEvent}
          hasNextEvent={!!nextEvent}
        />
      );
    default:
      return null;
  }
};

export default ModalManager; 