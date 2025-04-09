package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"writehere-go/internal/server"
	"writehere-go/pkg/log"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile  string
	logLevel string
	port     int
)

// rootCmd represents the base command when called without any subcommands
var rootCmd = &cobra.Command{
	Use:   "writehere-backend",
	Short: "Backend server for the WriteHERE application",
	Long:  `Runs the mock backend server providing API and WebSocket endpoints.`,
	PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
		// Setup logger early
		log.SetupLogger(logLevel)
		return nil
	},
	RunE: func(cmd *cobra.Command, args []string) error {
		// Create context that listens for the interrupt signal from the OS.
		ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
		defer stop() // Release resources associated with signal listening

		log.Log.Info().Msg("Starting application with root context")

		cfg := server.Config{
			Port:     port,
			LogLevel: logLevel,
		}

		if err := server.Run(ctx, cfg); err != nil {
			// Check if the error is due to context cancellation (expected on shutdown)
			if errors.Is(err, context.Canceled) {
				log.Log.Info().Msg("Server shutdown initiated by context cancellation.")
				return nil // Clean exit
			} else {
				log.Log.Error().Err(err).Msg("Server run failed")
				return fmt.Errorf("server run failed: %w", err)
			}
		}

		log.Log.Info().Msg("Application finished cleanly")
		return nil
	},
}

// Execute adds all child commands to the root command and sets flags appropriately.
// This is called by main.main(). It only needs to happen once to the rootCmd.
func Execute() {
	err := rootCmd.Execute()
	if err != nil {
		// Cobra already prints the error, just exit
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	// Persistent flags, available to this command and all subcommands
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.writehere-backend.yaml)")
	rootCmd.PersistentFlags().StringVar(&logLevel, "log-level", "info", "Set the logging level (debug, info, warn, error, fatal, panic)")

	// Local flags, only available to this command
	rootCmd.Flags().IntVarP(&port, "port", "p", 5001, "Port to run the server on")

	// Bind flags to viper (optional, if using config file)
	// viper.BindPFlag("log.level", rootCmd.PersistentFlags().Lookup("log-level"))
	// viper.BindPFlag("server.port", rootCmd.Flags().Lookup("port"))
}

// initConfig reads in config file and ENV variables if set.
func initConfig() {
	if cfgFile != "" {
		// Use config file from the flag.
		viper.SetConfigFile(cfgFile)
	} else {
		// Find home directory.
		home, err := os.UserHomeDir()
		cobra.CheckErr(err)

		// Search config in home directory with name ".writehere-backend" (without extension).
		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".writehere-backend")
	}

	viper.AutomaticEnv() // read in environment variables that match

	// If a config file is found, read it in.
	if err := viper.ReadInConfig(); err == nil {
		log.Log.Debug().Str("configFile", viper.ConfigFileUsed()).Msg("Using config file")
		// You might want to override flags with config values here
		// port = viper.GetInt("server.port")
		// logLevel = viper.GetString("log.level")
	}
}

func main() {
	Execute()
}
