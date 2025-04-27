Below is a design + bare-bones code skeleton that shows how to port the **Python WebSocket server** to **Go** using **Watermill** so that every backend component consumes the same Redis-stream message **directly through Watermill’s router**—no ad-hoc `chan …` plumbing required—while 100 % preserving the
existing Redis message format (`XADD agent_events * json_payload="<raw-json>"`).

---

## 1. Key ideas

| Concern | How it works with Watermill |
|---------|----------------------------|
| **Single source of truth** | `redisstream.PubSub` subscribes to the *exact* Redis stream `agent_events`. Every Watermill handler gets its own copy of the **same** message object; no extra fan-out channels. |
| **Fan-out to subsystems** | Register three independent handlers on the same topic:<br>  1. **dbPersistHandler** – writes to SQLite.<br>  2. **stateUpdateHandler** – mutates in-memory Event/Graph managers.<br>  3. **wsBroadcastHandler** – pushes the *raw* JSON to the WebSocket hub. |
| **Back-pressure / retries** | Let Watermill’s middleware (ack/retry, dead-letter, poison-queue) handle it; you only decide per-handler if you `Ack()` or `Nack(err)`. |
| **No internal channels** | Every component **pulls** from Watermill, not from each other. The only “shared” objects are the state-manager instances guarded by mutexes. |
| **Same wire protocol** | Each handler reads `msg.Payload` (bytes) → `json.Unmarshal` into the existing `Event` struct. Nothing about the Redis entry changes. |

---

## 2. Package layout

```
cmd/
  server/
    main.go             ← wiring, config, shutdown
internal/
  api/
    handlers.go         ← HTTP/REST endpoints
  ws/
    hub.go              ← gorilla/websocket hub
  redis/
    listener.go         ← Watermill router + handlers
  db/
    manager.go          ← SQLite storage (port of Python logic)
  state/
    event_manager.go
    graph_manager.go
pkg/
  model/
    event.go            ← Go version of Event struct
  config/
    config.go           ← mirrors ServerConfig
```

---

## 3. Minimal working skeleton

```go
// go:1.22
package main

import (
	"context"
	"database/sql"
	"net/http"

	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog/log"
	"github.com/ThreeDotsLabs/watermill"
	"github.com/ThreeDotsLabs/watermill/message"
	"github.com/ThreeDotsLabs/watermill/message/router"
	"github.com/ThreeDotsLabs/watermill/message/infrastructure/redisstream"

	"myapp/internal/db"
	"myapp/internal/state"
	"myapp/internal/ws"
	"myapp/pkg/config"
	"myapp/pkg/model"
)

func main() {
	cfg := config.FromEnv()               // exact env vars used by Python
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// ------------------------------------------------------------------ //
	// 1.  Build Watermill infrastructure
	// ------------------------------------------------------------------ //
	wlog  := watermill.NewStdLogger(cfg.Debug, cfg.Debug)          // Watermill logger
	pubSub, err := redisstream.NewPubSub(
		redisstream.Config{
			Client:      redisstream.NewClient(cfg.RedisURL),
			Consumer:    "go-ws-server",
			Group:       "go-ws-group",
			Marshaler:   redisstream.DefaultMarshaler{},
			Stream:      cfg.EventStream,          // "agent_events"
			AckOnError:  false,
		},
		wlog,
	)
	if err != nil { log.Fatal().Err(err).Msg("init redis") }

	r, err := router.NewRouter(router.Config{}, wlog)
	if err != nil { log.Fatal().Err(err).Msg("router") }

	// ------------------------------------------------------------------ //
	// 2.  Initialise shared state & DB
	// ------------------------------------------------------------------ //
	sqlite, err := sql.Open("sqlite3", cfg.DBPath)
	if err != nil { log.Fatal().Err(err) }
	dbm := db.NewManager(sqlite)
	evState := state.NewEventManager(200)
	grState := state.NewGraphManager()
	wsHub   := ws.NewHub()            // gorilla hub (start below)

	// Optionally reload latest session from DB here …
	// dbm.LoadLatestInto(evState, grState)

	// ------------------------------------------------------------------ //
	// 3.  Register handlers (fan-out) on the SAME topic
	// ------------------------------------------------------------------ //
	const topic = "agent_events"

	r.AddNoPublisherHandler(
		"db-persist",
		topic,
		pubSub,
		func(msg *message.Message) error {
			ev, err := model.Decode(msg.Payload)
			if err != nil { return err }      // nack -> retry
			if err := dbm.StoreEvent(ctx, ev); err != nil { return err }
			msg.Ack()
			return nil
		},
	)

	r.AddNoPublisherHandler(
		"state-update",
		topic,
		pubSub,
		func(msg *message.Message) error {
			ev, err := model.Decode(msg.Payload)
			if err != nil { return err }
			state.ApplyEvent(evState, grState, ev)
			msg.Ack()
			return nil
		},
	)

	r.AddNoPublisherHandler(
		"ws-broadcast",
		topic,
		pubSub,
		func(msg *message.Message) error {
			raw := append([]byte(nil), msg.Payload...) // copy
			wsHub.Broadcast(raw)                      // non-blocking
			msg.Ack()
			return nil
		},
	)

	// ------------------------------------------------------------------ //
	// 4.  Run everything
	// ------------------------------------------------------------------ //
	go wsHub.Run(ctx)                                    // websocket hub pumps

	go func() {
		if err := r.Run(ctx); err != nil {
			log.Error().Err(err).Msg("router run failed")
			cancel()
		}
	}()

	// start HTTP + WebSocket endpoints (static UI, /api/…, upgrade /ws/events)
	srv := &http.Server{
		Addr:    cfg.BindAddr(),   // host:port
		Handler: api.BuildMux(cfg, evState, grState, wsHub),
	}
	go func() {
		log.Info().Msgf("HTTP listening on %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error().Err(err).Msg("http server")
			cancel()
		}
	}()

	<-ctx.Done()
	_ = srv.Shutdown(context.Background())
	r.Close()       // flush router
	pubSub.Close()
	sqlite.Close()
}
```

### What changed vs. the Python server?

| Layer | Python | Go + Watermill |
|-------|--------|---------------|
| Redis → in-proc fan-out | `xread` + manual `for` loop pushing to different services | Watermill `router` + three independent handlers on the **same** topic |
| Back-pressure | `await connection.send_text` may drop on error | Watermill `Ack/Nack` + retry/dead-letter guarantees each handler sees the message once |
| Recovery on restart | Python reloads DB then replays events into memory | Same: call `dbm.LoadLatestInto` *before* starting the router |
| Internal plumbing | Sets & `asyncio.Lock` + explicit loops | Locks remain inside state-managers, **but** message flow uses Watermill—not custom channels |

---

## 4. Detailed implementation notes

1. **Redis Streams vs. Pub/Sub**  
   Watermill’s `redisstream` package works with *streams*, so it can join the existing  
   `XADD agent_events * json_payload="…"` workflow without modification.  
   Use `Group` + `Consumer` IDs so multiple server instances can each receive **all** messages
   (fan-out), not load-balance. Set `Block` to `0` for an infinite‐blocking read, mirroring `XREAD BLOCK 0`.

2. **Event decoding**  

   ```go
   func Decode(b []byte) (*model.Event, error) {
       var wrapper struct{ JsonPayload string `redis:"json_payload"` } // mimic original field
       if err := json.Unmarshal(b, &wrapper); err != nil {
           return nil, err
       }
       var ev model.Event
       if err := json.Unmarshal([]byte(wrapper.JsonPayload), &ev); err != nil {
           return nil, err
       }
       return &ev, nil
   }
   ```

   You purposely keep the *exact* `Event` fields (`event_id`, `timestamp`, `event_type`, `payload`, `run_id`) so other services stay compatible.

3. **SQLite logic** – port every `_handle_*` method from Python’s `DatabaseManager` almost verbatim; wrap each in a transaction and reuse prepared statements for speed.

4. **Graph/Event state managers** – direct 1-for-1 translation:
   * `EventManager` → slice + mutex  
   * `GraphManager` → two maps (`nodes`, `edges`) + mutex  
   Each Watermill handler call is already in its own goroutine, so internal locks are necessary.

5. **WebSocket Hub** – You can still reuse Gorilla’s canonical “hub” pattern (map of clients + broadcast chan) or, if you truly want *zero* channels, expose a `Broadcast([]byte)` that just loops over the `clients` map with its own lock.

6. **Graceful shutdown** – Watermill’s router respects `ctx.Done()`. Make the root context cancel when:
   * SIGINT / SIGTERM  
   * HTTP server returns fatal error  
   * Watermill router returns error

7. **Configuration parity** – `pkg/config` should read the *same* env variables as `ServerConfig.from_env` so docker-compose & k8s manifests stay untouched.
