package api

import (
	"fmt"
	"net/http"
	"sort"
	"strings"
	"time"

	"writehere-go/internal/models"
	"writehere-go/internal/task"
	"writehere-go/internal/websocket"
	"writehere-go/pkg/log"

	"github.com/gin-gonic/gin"
)

// API provides dependencies for the API handlers.
type API struct {
	TaskManager *task.MockTaskManager
	TaskStore   *models.TaskStore
	WSHub       *websocket.Hub
}

// NewAPI creates a new API instance.
func NewAPI(taskManager *task.MockTaskManager, taskStore *models.TaskStore, wsHub *websocket.Hub) *API {
	return &API{
		TaskManager: taskManager,
		TaskStore:   taskStore,
		WSHub:       wsHub,
	}
}

// RegisterRoutes sets up the API routes.
func (a *API) RegisterRoutes(router *gin.Engine) {
	api := router.Group("/api")
	{
		api.POST("/generate-story", a.GenerateStoryHandler)
		api.POST("/generate-report", a.GenerateReportHandler)
		api.GET("/status/:task_id", a.GetStatusHandler)
		api.GET("/result/:task_id", a.GetResultHandler)
		api.GET("/task-graph/:task_id", a.GetTaskGraphHandler)
		api.GET("/workspace/:task_id", a.GetWorkspaceHandler)
		api.GET("/history", a.GetHistoryHandler)
		api.POST("/reload", a.ReloadHandler) // Mocked
		api.POST("/stop-task/:task_id", a.StopTaskHandler)
		api.DELETE("/delete-task/:task_id", a.DeleteTaskHandler)
		api.GET("/ping", a.PingHandler)

		// WebSocket endpoint
		api.GET("/ws", a.WebSocketHandler)
	}
}

// GenerateStoryHandler handles requests to start a story generation task.
func (a *API) GenerateStoryHandler(c *gin.Context) {
	var req models.GenerateStoryRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Log.Error().Err(err).Msg("Invalid request body for generate-story")
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body: " + err.Error()})
		return
	}

	// Pass the request context to the task manager
	taskData, err := a.TaskManager.CreateStoryTask(c.Request.Context(), req.Prompt, req.Model)
	if err != nil {
		log.Log.Error().Err(err).Msg("Failed to create story task")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to start task: " + err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.TaskCreationResponse{
		TaskID: taskData.ID,
		Status: "started",
	})
}

// GenerateReportHandler handles requests to start a report generation task.
func (a *API) GenerateReportHandler(c *gin.Context) {
	var req models.GenerateReportRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Log.Error().Err(err).Msg("Invalid request body for generate-report")
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body: " + err.Error()})
		return
	}

	// Pass the request context to the task manager
	taskData, err := a.TaskManager.CreateReportTask(c.Request.Context(), req.Prompt, req.Model, req.EnableSearch, req.SearchEngine)
	if err != nil {
		log.Log.Error().Err(err).Msg("Failed to create report task")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to start task: " + err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.TaskCreationResponse{
		TaskID: taskData.ID,
		Status: "started",
	})
}

// GetStatusHandler returns the status of a specific task.
func (a *API) GetStatusHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	taskData, exists := a.TaskStore.GetTask(taskID)
	if !exists {
		errorResponse(c, http.StatusNotFound, "Task not found")
		return
	}

	// Recalculate elapsed time on each request
	elapsedTime := time.Since(taskData.StartTime).Seconds()

	c.JSON(http.StatusOK, models.TaskStatusResponse{
		TaskID:       taskData.ID,
		Status:       taskData.Status,
		Error:        taskData.Error,
		ElapsedTime:  elapsedTime,
		Model:        taskData.Model,
		SearchEngine: taskData.SearchEngine,
	})
}

// GetResultHandler returns the result of a completed task.
func (a *API) GetResultHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	taskData, exists := a.TaskStore.GetTask(taskID)
	if !exists {
		errorResponse(c, http.StatusNotFound, "Task not found")
		return
	}

	if taskData.Status != models.StatusCompleted && taskData.Status != models.StatusError && taskData.Status != models.StatusStopped {
		errorResponse(c, http.StatusBadRequest, fmt.Sprintf("Task result not available yet (status: %s)", taskData.Status))
		return
	}

	// For stopped tasks, the result is set in handleStop
	// For error tasks, the result is empty, but the Error field is set

	c.JSON(http.StatusOK, models.TaskResultResponse{
		TaskID:       taskData.ID,
		Result:       taskData.Result, // Contains mock result or stopped message
		Model:        taskData.Model,
		SearchEngine: taskData.SearchEngine,
	})
}

// GetTaskGraphHandler returns the mock task graph for a task.
func (a *API) GetTaskGraphHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	taskData, exists := a.TaskStore.GetTask(taskID)
	if !exists {
		errorResponse(c, http.StatusNotFound, "Task not found")
		return
	}

	c.JSON(http.StatusOK, models.TaskGraphResponse{
		TaskID:    taskData.ID,
		TaskGraph: taskData.MockGraph, // Return the current mock graph
	})
}

// GetWorkspaceHandler returns the mock workspace content for a task.
func (a *API) GetWorkspaceHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	taskData, exists := a.TaskStore.GetTask(taskID)
	if !exists {
		errorResponse(c, http.StatusNotFound, "Task not found")
		return
	}

	c.JSON(http.StatusOK, models.WorkspaceResponse{
		TaskID:    taskData.ID,
		Workspace: taskData.MockWorkspace, // Return the current mock workspace
	})
}

// GetHistoryHandler returns a list of all tasks.
func (a *API) GetHistoryHandler(c *gin.Context) {
	tasks := a.TaskStore.ListTasks()

	// Sort tasks by StartTime descending (newest first)
	sort.Slice(tasks, func(i, j int) bool {
		return tasks[i].StartTime.After(tasks[j].StartTime)
	})

	historyItems := make([]models.HistoryItem, len(tasks))
	for i, t := range tasks {
		historyItems[i] = models.HistoryItem{
			TaskID:    t.ID,
			Prompt:    task.TruncatePrompt(t.Prompt, 100),
			Type:      t.Type,
			CreatedAt: t.StartTime.Format(time.RFC3339), // Use standard format
		}
	}

	c.JSON(http.StatusOK, models.HistoryResponse{
		History: historyItems,
	})
}

// ReloadHandler is a mocked endpoint.
func (a *API) ReloadHandler(c *gin.Context) {
	log.Log.Info().Msg("Received request to /api/reload (mocked, no action taken)")
	c.JSON(http.StatusOK, models.SimpleResponse{
		Status:  "ok",
		Message: "Task storage reload not implemented in mock server",
	})
}

// StopTaskHandler handles requests to stop a running task.
func (a *API) StopTaskHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	err := a.TaskManager.StopTask(taskID)
	if err != nil {
		log.Log.Error().Err(err).Str("taskId", taskID).Msg("Failed to stop task")
		// Determine if it's a 404 or other error
		if strings.Contains(err.Error(), "not found") {
			errorResponse(c, http.StatusNotFound, err.Error())
		} else {
			errorResponse(c, http.StatusBadRequest, err.Error())
		}
		return
	}

	c.JSON(http.StatusOK, models.SimpleResponse{
		Status:  "ok",
		Message: fmt.Sprintf("Task %s stop signal sent", taskID),
	})
}

// DeleteTaskHandler handles requests to delete a task.
func (a *API) DeleteTaskHandler(c *gin.Context) {
	taskID := c.Param("task_id")
	err := a.TaskManager.DeleteTask(taskID)
	if err != nil {
		log.Log.Error().Err(err).Str("taskId", taskID).Msg("Failed to delete task")
		errorResponse(c, http.StatusNotFound, err.Error()) // Assume 404 for delete errors
		return
	}

	c.JSON(http.StatusOK, models.SimpleResponse{
		Status:  "ok",
		Message: fmt.Sprintf("Task %s deleted successfully", taskID),
	})
}

// PingHandler is a simple health check endpoint.
func (a *API) PingHandler(c *gin.Context) {
	c.JSON(http.StatusOK, models.PingResponse{
		Status:  "ok",
		Message: "API server is running",
		Version: "1.0.0-mock",
	})
}

// WebSocketHandler upgrades the connection to WebSocket.
func (a *API) WebSocketHandler(c *gin.Context) {
	websocket.ServeWs(a.WSHub, c.Writer, c.Request)
}

// Helper for error responses
func errorResponse(c *gin.Context, code int, message string) {
	log.Log.Error().Int("status", code).Str("path", c.Request.URL.Path).Msg(message)
	c.JSON(code, gin.H{"error": message})
}
