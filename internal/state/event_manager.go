package state

import (
	"sync"

	"github.com/rs/zerolog"

	"writehere-go/pkg/model"
)

// EventManager manages the in-memory state of events for the current session
type EventManager struct {
	events  []model.Event
	mutex   sync.RWMutex
	logger  zerolog.Logger
	maxSize int
}

// NewEventManager creates a new event manager with the specified max event history size
func NewEventManager(logger zerolog.Logger, maxSize int) *EventManager {
	if maxSize <= 0 {
		maxSize = 1000 // Default to 1000 events maximum
	}

	return &EventManager{
		events:  make([]model.Event, 0, 100), // Pre-allocate space for 100 events
		mutex:   sync.RWMutex{},
		logger:  logger.With().Str("component", "event_manager").Logger(),
		maxSize: maxSize,
	}
}

// AddEvent adds a new event to the in-memory state
func (m *EventManager) AddEvent(event model.Event) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Add the event to the list
	m.events = append(m.events, event)

	// If we've exceeded the maximum size, remove oldest events
	if len(m.events) > m.maxSize {
		excess := len(m.events) - m.maxSize
		m.events = m.events[excess:]
		m.logger.Debug().
			Int("removed", excess).
			Int("new_size", len(m.events)).
			Msg("Removed oldest events to stay within max size")
	}
}

// GetEvents returns a copy of the current events list
func (m *EventManager) GetEvents() []model.Event {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	// Create a copy to avoid external modification
	eventsCopy := make([]model.Event, len(m.events))
	copy(eventsCopy, m.events)

	return eventsCopy
}

// GetEventCount returns the number of events currently stored
func (m *EventManager) GetEventCount() int {
	m.mutex.RLock()
	defer m.mutex.RUnlock()

	return len(m.events)
}

// Clear removes all events from the manager
func (m *EventManager) Clear() {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Reset the slice, but maintain capacity
	m.events = m.events[:0]
}

// LoadStateFromDB populates the event manager with events from the database
// This function is used when reloading an existing session
func (m *EventManager) LoadStateFromDB(events []model.Event) {
	m.mutex.Lock()
	defer m.mutex.Unlock()

	// Reset current state
	m.events = make([]model.Event, 0, len(events))

	// Add each event from the database
	for _, event := range events {
		m.events = append(m.events, event)
	}

	m.logger.Info().
		Int("event_count", len(m.events)).
		Msg("Loaded events from database")
}
