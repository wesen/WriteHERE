package log

import (
	"os"
	"time"

	"github.com/rs/zerolog"
)

var Log zerolog.Logger

func SetupLogger(level string) {
	lvl, err := zerolog.ParseLevel(level)
	if err != nil {
		lvl = zerolog.InfoLevel
	}

	output := zerolog.ConsoleWriter{Out: os.Stdout, TimeFormat: time.RFC3339}
	Log = zerolog.New(output).Level(lvl).With().Timestamp().Caller().Logger()

	Log.Info().Str("logLevel", lvl.String()).Msg("Logger initialized")
}
