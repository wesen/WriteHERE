import React, { useEffect } from 'react';
import NodeDetailModal from './NodeDetailModal';
import EventDetailModal from './EventDetailModal';
import { useAppSelector, useAppDispatch } from '../store';
import { pushModal, popModal, clearStack } from '../features/ui/modalStackSlice';
import { useGetEventsQuery } from '../features/events/eventsApi';

export const ModalManager: React.FC = () => {
  const dispatch = useAppDispatch();
  const stack = useAppSelector(s => s.modalStack.stack);
  const top = stack[stack.length - 1];
  const { data: eventsData } = useGetEventsQuery();

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
      
      return (
        <EventDetailModal
          show
          onHide={onHide}
          event={event}
          onNodeClick={onNodeClick}
          hasPrevious={stack.length > 1}
          onBack={onBack}
        />
      );
    default:
      return null;
  }
};

export default ModalManager; 