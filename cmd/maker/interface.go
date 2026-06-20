package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"html/template"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

type interfaceOptions struct {
	EventCount     int
	WakeCount      int
	FieldNoteCount int
	WorldDepth     int
	RefreshSeconds int
	OutputPath     string
	Serve          bool
	Detach         bool
	Stop           bool
	StartLoop      bool
	Host           string
	Port           int
	PublishWorld   bool
	WorldNotePath  string
}

type finnInterfaceSnapshot struct {
	GeneratedAt        string                    `json:"generated_at"`
	MakerPlace         string                    `json:"maker_place"`
	RefreshSeconds     int                       `json:"refresh_seconds"`
	Runtime            finnInterfaceRuntime      `json:"runtime"`
	Totals             finnInterfaceTotals       `json:"totals"`
	LatestWake         finnInterfaceWake         `json:"latest_wake"`
	Thinking           []finnInterfaceText       `json:"thinking"`
	Thoughts           []finnInterfaceText       `json:"thoughts"`
	Creations          []finnInterfaceCreation   `json:"creations"`
	Friends            []finnInterfaceEntity     `json:"friends"`
	Creatures          []finnInterfaceEntity     `json:"creatures"`
	Places             []finnInterfaceEntity     `json:"places"`
	FieldNotes         []finnInterfaceNote       `json:"field_notes"`
	RecentWakes        []finnInterfaceWake       `json:"recent_wakes"`
	RecentEvents       []finnInterfaceEvent      `json:"recent_events"`
	World              finnInterfaceWorld        `json:"world"`
	Health             []finnInterfaceSignal     `json:"health"`
	WorldNotePath      string                    `json:"world_note_path,omitempty"`
	WorldNotePublished bool                      `json:"world_note_published"`
	WorldNoteError     string                    `json:"world_note_error,omitempty"`
	ToolCounts         []finnInterfaceMetricPair `json:"tool_counts"`
}

type finnInterfaceRuntime struct {
	Label       string `json:"label"`
	Detail      string `json:"detail"`
	Class       string `json:"class"`
	Controller  string `json:"controller"`
	WakeLock    string `json:"wake_lock"`
	Sandbox     string `json:"sandbox"`
	LatestEvent string `json:"latest_event"`
}

type finnInterfaceTotals struct {
	Wakes           int `json:"wakes"`
	ProductiveWakes int `json:"productive_wakes"`
	ModelResponses  int `json:"model_responses"`
	TextOutputs     int `json:"text_outputs"`
	ToolCalls       int `json:"tool_calls"`
	WorldMutations  int `json:"world_mutations"`
	Errors          int `json:"errors"`
	WorldEntries    int `json:"world_entries"`
}

type finnInterfaceWake struct {
	Present        bool     `json:"present"`
	ID             string   `json:"id"`
	Model          string   `json:"model"`
	Started        string   `json:"started"`
	Ended          string   `json:"ended"`
	Duration       string   `json:"duration"`
	Reason         string   `json:"reason"`
	Assessment     string   `json:"assessment"`
	StateClass     string   `json:"state_class"`
	ToolCount      int      `json:"tool_count"`
	TextCount      int      `json:"text_count"`
	ModelResponses int      `json:"model_responses"`
	WorldChanged   bool     `json:"world_changed"`
	Errors         int      `json:"errors"`
	ToolSequence   []string `json:"tool_sequence"`
	DiffPreview    []string `json:"diff_preview"`
}

type finnInterfaceText struct {
	Source    string `json:"source"`
	WakeID    string `json:"wake_id"`
	Preview   string `json:"preview"`
	Bytes     int    `json:"bytes"`
	Truncated bool   `json:"truncated"`
}

type finnInterfaceCreation struct {
	Kind   string `json:"kind"`
	Name   string `json:"name"`
	Path   string `json:"path"`
	WakeID string `json:"wake_id"`
	Detail string `json:"detail"`
	Status string `json:"status"`
}

type finnInterfaceEntity struct {
	Name   string `json:"name"`
	Kind   string `json:"kind"`
	Source string `json:"source"`
	Detail string `json:"detail"`
}

type finnInterfaceNote struct {
	ID      string `json:"id"`
	Path    string `json:"path"`
	Title   string `json:"title"`
	Preview string `json:"preview"`
}

type finnInterfaceEvent struct {
	Time   string `json:"time"`
	Type   string `json:"type"`
	WakeID string `json:"wake_id"`
	Detail string `json:"detail"`
	Level  string `json:"level"`
}

type finnInterfaceWorld struct {
	OK      bool     `json:"ok"`
	Error   string   `json:"error,omitempty"`
	Entries []string `json:"entries"`
	Count   int      `json:"count"`
}

type finnInterfaceSignal struct {
	Label  string `json:"label"`
	Detail string `json:"detail"`
	Level  string `json:"level"`
}

type finnInterfaceMetricPair struct {
	Name  string `json:"name"`
	Count int    `json:"count"`
}

func cmdInterface(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	opts := interfaceOptions{}
	fs := flag.NewFlagSet("interface", flag.ContinueOnError)
	fs.IntVar(&opts.EventCount, "events", 28, "recent events to show")
	fs.IntVar(&opts.WakeCount, "wakes", 12, "recent wakes to show")
	fs.IntVar(&opts.FieldNoteCount, "field-notes", 6, "recent field notes to show")
	fs.IntVar(&opts.WorldDepth, "world-depth", 4, "maximum Docker world find depth")
	fs.IntVar(&opts.RefreshSeconds, "refresh", 5, "HTML refresh interval in seconds")
	fs.StringVar(&opts.OutputPath, "output", "", "write static HTML to this file")
	fs.BoolVar(&opts.Serve, "serve", false, "serve a live local HTML interface")
	fs.BoolVar(&opts.Detach, "detach", false, "start the interface server in the background")
	fs.BoolVar(&opts.Stop, "stop", false, "stop a detached interface server")
	fs.BoolVar(&opts.StartLoop, "start-loop", false, "start Finn with local settings that inspect the published interface note each wake")
	fs.StringVar(&opts.Host, "host", "127.0.0.1", "interface server host")
	fs.IntVar(&opts.Port, "port", 8765, "interface server port")
	fs.BoolVar(&opts.PublishWorld, "publish-world", false, "write a Finn-readable interface snapshot into the Docker world")
	fs.StringVar(&opts.WorldNotePath, "world-note", "_maker/interface-status.md", "relative /world path for --publish-world")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if fs.NArg() > 0 {
		return fmt.Errorf("interface does not accept positional arguments")
	}
	if opts.EventCount < 1 {
		opts.EventCount = 1
	}
	if opts.WakeCount < 1 {
		opts.WakeCount = 1
	}
	if opts.FieldNoteCount < 0 {
		opts.FieldNoteCount = 0
	}
	if opts.WorldDepth < 1 {
		opts.WorldDepth = 1
	}
	if opts.RefreshSeconds < 0 {
		opts.RefreshSeconds = 0
	}
	if opts.Stop {
		return stopDetachedFinnInterface(cfg, out)
	}
	if opts.StartLoop {
		return startFinnInterfaceLoop(cfg, opts, out)
	}
	if opts.Detach {
		if !opts.Serve {
			return errors.New("--detach requires --serve")
		}
		return detachFinnInterface(cfg, opts, out)
	}
	if opts.Serve {
		return serveFinnInterface(cfg, opts, out)
	}

	snapshot := buildFinnInterfaceSnapshot(cfg, opts)
	if opts.PublishWorld {
		if err := publishFinnInterfaceSnapshot(cfg, opts.WorldNotePath, snapshot); err != nil {
			snapshot.WorldNoteError = err.Error()
		} else {
			snapshot.WorldNotePublished = true
			snapshot.WorldNotePath = opts.WorldNotePath
		}
	}
	if cfg.JSON {
		return writeJSON(out, snapshot)
	}
	html, err := renderFinnInterfaceHTML(snapshot)
	if err != nil {
		return err
	}
	if opts.OutputPath != "" {
		if err := os.MkdirAll(filepath.Dir(opts.OutputPath), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(opts.OutputPath, []byte(html), 0o644); err != nil {
			return err
		}
		fmt.Fprintf(out, "interface written: %s\n", opts.OutputPath)
		if snapshot.WorldNotePublished {
			fmt.Fprintf(out, "world snapshot published: /world/%s\n", snapshot.WorldNotePath)
		}
		if snapshot.WorldNoteError != "" {
			fmt.Fprintf(out, "world snapshot failed: %s\n", snapshot.WorldNoteError)
		}
		return nil
	}
	fmt.Fprint(out, html)
	return nil
}

func interfaceServerPaths(cfg Config) (string, string, string) {
	dir := filepath.Join(cfg.MakerPlace, "interface")
	return dir, filepath.Join(dir, "server.pid"), filepath.Join(dir, "server.log")
}

func detachFinnInterface(cfg Config, opts interfaceOptions, out io.Writer) error {
	if opts.Port == 0 {
		return errors.New("--detach requires a fixed --port")
	}
	dir, pidPath, logPath := interfaceServerPaths(cfg)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	if pidInfo := readPID(pidPath); pidInfo["running"] == true {
		fmt.Fprintf(out, "interface server already running: %v\n", pidInfo["pid"])
		fmt.Fprintf(out, "url: http://%s:%d\n", opts.Host, opts.Port)
		fmt.Fprintf(out, "log: %s\n", logPath)
		return nil
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	args := []string{
		"--maker-place", cfg.MakerPlace,
		"--world-volume", cfg.WorldVolume,
		"--sandbox-image", cfg.SandboxImage,
		"interface",
		"--serve",
		"--host", opts.Host,
		"--port", strconv.Itoa(opts.Port),
		"--events", strconv.Itoa(opts.EventCount),
		"--wakes", strconv.Itoa(opts.WakeCount),
		"--field-notes", strconv.Itoa(opts.FieldNoteCount),
		"--world-depth", strconv.Itoa(opts.WorldDepth),
		"--refresh", strconv.Itoa(opts.RefreshSeconds),
		"--world-note", opts.WorldNotePath,
	}
	if opts.PublishWorld {
		args = append(args, "--publish-world")
	}
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer logFile.Close()
	cmd := exec.Command(exe, args...)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Env = os.Environ()
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		return err
	}
	pid := cmd.Process.Pid
	if err := os.WriteFile(pidPath, []byte(strconv.Itoa(pid)+"\n"), 0o644); err != nil {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		return err
	}
	if err := cmd.Process.Release(); err != nil {
		return err
	}
	fmt.Fprintf(out, "interface server started: %d\n", pid)
	fmt.Fprintf(out, "url: http://%s:%d\n", opts.Host, opts.Port)
	fmt.Fprintf(out, "log: %s\n", logPath)
	return nil
}

func stopDetachedFinnInterface(cfg Config, out io.Writer) error {
	_, pidPath, _ := interfaceServerPaths(cfg)
	pidInfo := readPID(pidPath)
	pid := number(pidInfo["pid"])
	if pidInfo["running"] == true && pid > 0 {
		_ = syscall.Kill(pid, syscall.SIGTERM)
		for i := 0; i < 20; i++ {
			if !pidRunning(pid) {
				break
			}
			time.Sleep(100 * time.Millisecond)
		}
		if pidRunning(pid) {
			_ = syscall.Kill(pid, syscall.SIGKILL)
		}
	}
	if pidInfo["exists"] == true {
		_ = os.Remove(pidPath)
	}
	fmt.Fprintln(out, "interface server stopped")
	return nil
}

func startFinnInterfaceLoop(cfg Config, opts interfaceOptions, out io.Writer) error {
	snapshot := buildFinnInterfaceSnapshot(cfg, opts)
	if err := publishFinnInterfaceSnapshot(cfg, opts.WorldNotePath, snapshot); err != nil {
		return err
	}
	fmt.Fprintf(out, "world snapshot published: /world/%s\n", opts.WorldNotePath)
	overrides := map[string]string{
		"MODEL_PROVIDER":                      "ollama",
		"WAKE_INTERVAL_SECONDS":               "0",
		"FIRST_MODEL_TOOL_CHOICE":             "function:read_file",
		"FIRST_MODEL_TOOL_ARGS_JSON":          fmt.Sprintf(`{"path":%q}`, opts.WorldNotePath),
		"FIRST_MODEL_TOOL_STRICT":             "1",
		"POST_FIRST_TOOL_SCHEMA_MODE":         "write-only",
		"MODEL_TOOL_CHOICE":                   "function:write_file",
		"MAX_TOOL_CALLS_PER_WAKE":             "2",
		"MAX_CONSECUTIVE_TEXT_ONLY_RESPONSES": "1",
	}
	restore := applyTemporaryEnv(overrides)
	defer restore()
	return cmdStart(cfg, []string{}, out)
}

func applyTemporaryEnv(values map[string]string) func() {
	type previousValue struct {
		value   string
		existed bool
	}
	previous := map[string]previousValue{}
	for key, value := range values {
		old, existed := os.LookupEnv(key)
		previous[key] = previousValue{value: old, existed: existed}
		_ = os.Setenv(key, value)
	}
	return func() {
		for key, old := range previous {
			if old.existed {
				_ = os.Setenv(key, old.value)
			} else {
				_ = os.Unsetenv(key)
			}
		}
	}
}

func serveFinnInterface(cfg Config, opts interfaceOptions, out io.Writer) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		snapshot := buildFinnInterfaceSnapshot(cfg, opts)
		if opts.PublishWorld {
			if err := publishFinnInterfaceSnapshot(cfg, opts.WorldNotePath, snapshot); err != nil {
				snapshot.WorldNoteError = err.Error()
			} else {
				snapshot.WorldNotePublished = true
				snapshot.WorldNotePath = opts.WorldNotePath
			}
		}
		html, err := renderFinnInterfaceHTML(snapshot)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(html))
	})
	mux.HandleFunc("/data.json", func(w http.ResponseWriter, r *http.Request) {
		snapshot := buildFinnInterfaceSnapshot(cfg, opts)
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = writeJSON(w, snapshot)
	})
	mux.HandleFunc("/favicon.ico", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	})

	addr := net.JoinHostPort(opts.Host, strconv.Itoa(opts.Port))
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	displayHost := opts.Host
	if displayHost == "0.0.0.0" || displayHost == "::" {
		displayHost = "127.0.0.1"
	}
	_, port, _ := net.SplitHostPort(listener.Addr().String())
	fmt.Fprintf(out, "Finn interface: http://%s:%s\n", displayHost, port)
	fmt.Fprintln(out, "Press Ctrl+C to stop the interface server.")
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	return server.Serve(listener)
}

func buildFinnInterfaceSnapshot(cfg Config, opts interfaceOptions) finnInterfaceSnapshot {
	events, eventsErr := readEvents(cfg, strings.NewReader(""))
	if eventsErr != nil && errors.Is(eventsErr, os.ErrNotExist) {
		events = []Event{}
	}
	wakes, wakesErr := loadWakeSummaries(cfg)
	if wakesErr != nil {
		wakes = []map[string]any{}
	}
	lock, _ := readJSONFile(filepath.Join(cfg.MakerPlace, "wake.lock"))
	pidInfo := readPID(filepath.Join(cfg.MakerPlace, "controller.pid"))
	containers := dockerLines("ps", "--format", "{{.Names}}\t{{.Status}}", "--filter", "label=maker.runtime=finn")
	latest, _ := latestEvent(defaultEventsPath(cfg))
	label, detail, _ := dashboardRuntimeStateParts(lock, pidInfo, containers)
	world := inspectInterfaceWorld(cfg, opts.WorldDepth)
	fieldNotes := recentInterfaceFieldNotes(cfg, opts.FieldNoteCount)
	recentWakes := interfaceRecentWakes(wakes, events, opts.WakeCount)
	latestWake := finnInterfaceWake{Present: false, Assessment: "No wake summary is available yet."}
	if len(lock) > 0 {
		latestWake = interfaceWakeFromActiveLock(lock, events)
	} else if len(wakes) > 0 {
		latestWake = interfaceWakeFromSummary(wakes[len(wakes)-1], events, len(lock) > 0)
	}
	thinking := interfaceThinking(events, resolveInterfaceWakeID(wakes, lock), opts.EventCount)
	thoughts := interfaceThoughts(wakes, opts.WakeCount)
	creations := interfaceCreations(wakes, opts.WakeCount)
	toolCounts := interfaceToolCounts(wakes)
	totals := interfaceTotals(wakes, events, world, toolCounts)
	friends := extractInterfaceEntities("friend", world.Entries, thoughts, fieldNotes, []string{
		"friend", "ally", "companion", "neighbor", "family", "village", "colony",
	}, 8)
	creatures := extractInterfaceEntities("creature", world.Entries, thoughts, fieldNotes, []string{
		"creature", "being", "animal", "avatar", "character", "entity", "life", "organism",
	}, 8)
	places := interfacePlaces(world.Entries, 10)
	health := interfaceHealth(label, eventsErr, wakesErr, latestWake, totals)

	runtime := finnInterfaceRuntime{
		Label:      label,
		Detail:     detail,
		Class:      interfaceClass(label),
		Controller: pidInfoText(pidInfo),
		WakeLock:   "none",
		Sandbox:    "none",
	}
	if len(lock) > 0 {
		runtime.WakeLock = fmt.Sprintf("wake=%s pid=%v started=%s", str(lock["wake_id"]), lock["pid"], str(lock["started_at"]))
	}
	if len(containers) > 0 {
		runtime.Sandbox = strings.Join(containers, "; ")
	}
	if latest != nil {
		runtime.LatestEvent = fmt.Sprintf("%s %s wake=%s", str(latest["time"]), str(latest["type"]), str(latest["wake_id"]))
	}

	return finnInterfaceSnapshot{
		GeneratedAt:    time.Now().Format(time.RFC3339),
		MakerPlace:     cfg.MakerPlace,
		RefreshSeconds: opts.RefreshSeconds,
		Runtime:        runtime,
		Totals:         totals,
		LatestWake:     latestWake,
		Thinking:       thinking,
		Thoughts:       thoughts,
		Creations:      creations,
		Friends:        friends,
		Creatures:      creatures,
		Places:         places,
		FieldNotes:     fieldNotes,
		RecentWakes:    recentWakes,
		RecentEvents:   interfaceRecentEvents(events, opts.EventCount),
		World:          world,
		Health:         health,
		ToolCounts:     toolCounts,
	}
}

func interfaceWakeFromSummary(wake map[string]any, events []Event, active bool) finnInterfaceWake {
	wakeID := str(wake["wake_id"])
	counts := countForWake(events, wakeID)
	diff, _ := wake["diff_summary"].(map[string]any)
	worldChanged := boolValue(diff["changed"])
	errorsCount := lenArray(wake["errors"])
	assessment := dashboardAssessment(counts, worldChanged, errorsCount, active)
	stateClass := "neutral"
	if errorsCount > 0 || countInt(counts, "controller_errors") > 0 {
		stateClass = "bad"
	} else if worldChanged {
		stateClass = "good"
	} else if lenArray(wake["tool_calls"]) > 0 {
		stateClass = "work"
	} else if lenArray(wake["text_outputs"]) > 0 {
		stateClass = "warn"
	}
	toolSequence := []string{}
	for _, item := range anySlice(wake["tool_calls"]) {
		call, _ := item.(map[string]any)
		name := str(call["name"])
		if name != "" {
			toolSequence = append(toolSequence, name)
		}
	}
	diffPreview := []string{}
	for _, line := range anySlice(diff["diff_preview"]) {
		diffPreview = append(diffPreview, compactOneLine(str(line), 180))
	}
	model := strings.TrimLeft(str(wake["model_provider"])+"/"+str(wake["model"]), "/")
	return finnInterfaceWake{
		Present:        true,
		ID:             wakeID,
		Model:          model,
		Started:        str(wake["start_time"]),
		Ended:          str(wake["end_time"]),
		Duration:       durationText(str(wake["start_time"]), str(wake["end_time"])),
		Reason:         fallbackText(str(wake["end_reason"]), "unknown"),
		Assessment:     assessment,
		StateClass:     stateClass,
		ToolCount:      lenArray(wake["tool_calls"]),
		TextCount:      lenArray(wake["text_outputs"]),
		ModelResponses: lenArray(wake["model_responses"]),
		WorldChanged:   worldChanged,
		Errors:         errorsCount,
		ToolSequence:   toolSequence,
		DiffPreview:    diffPreview,
	}
}

func interfaceWakeFromActiveLock(lock map[string]any, events []Event) finnInterfaceWake {
	wakeID := str(lock["wake_id"])
	counts := countForWake(events, wakeID)
	toolSequence := []string{}
	model := ""
	for _, event := range events {
		if str(event["wake_id"]) != wakeID {
			continue
		}
		if str(event["type"]) == "wake_start" {
			model = strings.TrimLeft(str(event["model_provider"])+"/"+str(event["model"]), "/")
		}
		if str(event["type"]) == "tool_call" {
			tool := str(event["tool"])
			if tool != "" {
				toolSequence = append(toolSequence, tool)
			}
		}
	}
	if model == "" {
		model = "unknown"
	}
	stateClass := "warn"
	if countInt(counts, "tool_calls") > 0 {
		stateClass = "work"
	}
	if countInt(counts, "model_errors") > 0 || countInt(counts, "controller_errors") > 0 {
		stateClass = "bad"
	}
	return finnInterfaceWake{
		Present:        true,
		ID:             wakeID,
		Model:          model,
		Started:        str(lock["started_at"]),
		Ended:          "still running",
		Duration:       durationText(str(lock["started_at"]), ""),
		Reason:         "running",
		Assessment:     activeWakeAssessment(counts),
		StateClass:     stateClass,
		ToolCount:      countInt(counts, "tool_calls"),
		TextCount:      countInt(counts, "model_text"),
		ModelResponses: countInt(counts, "model_responses"),
		WorldChanged:   false,
		Errors:         countInt(counts, "model_errors") + countInt(counts, "controller_errors"),
		ToolSequence:   toolSequence,
	}
}

func interfaceRecentWakes(wakes []map[string]any, events []Event, limit int) []finnInterfaceWake {
	items := []finnInterfaceWake{}
	start := len(wakes) - limit
	if start < 0 {
		start = 0
	}
	for i := len(wakes) - 1; i >= start; i-- {
		items = append(items, interfaceWakeFromSummary(wakes[i], events, false))
	}
	return items
}

func resolveInterfaceWakeID(wakes []map[string]any, lock map[string]any) string {
	if wakeID := str(lock["wake_id"]); wakeID != "" {
		return wakeID
	}
	if len(wakes) == 0 {
		return ""
	}
	return str(wakes[len(wakes)-1]["wake_id"])
}

func interfaceThinking(events []Event, wakeID string, limit int) []finnInterfaceText {
	if wakeID == "" {
		return []finnInterfaceText{}
	}
	responseEvents := recentResponseEvents(events, wakeID, limit)
	items := []finnInterfaceText{}
	for _, event := range responseEvents {
		kind := str(event["type"])
		switch kind {
		case "model_text":
			payload, _ := event["text"].(map[string]any)
			items = append(items, finnInterfaceText{
				Source:    "model text",
				WakeID:    str(event["wake_id"]),
				Preview:   compactOneLine(str(payload["preview"]), 360),
				Bytes:     number(payload["bytes"]),
				Truncated: boolValue(payload["truncated"]),
			})
		case "model_response":
			items = append(items, finnInterfaceText{
				Source:  "model response",
				WakeID:  str(event["wake_id"]),
				Preview: fmt.Sprintf("model=%s finish=%s tool_calls=%v", str(event["model"]), str(event["finish_reason"]), event["tool_call_count"]),
			})
		case "tool_call":
			items = append(items, finnInterfaceText{
				Source:  "tool call",
				WakeID:  str(event["wake_id"]),
				Preview: fmt.Sprintf("%s %s", str(event["tool"]), compactOneLine(compactJSON(event["arguments"]), 260)),
			})
		case "required_tool_choice_ignored", "model_text_only", "text_tool_call_promoted":
			items = append(items, finnInterfaceText{
				Source:  strings.ReplaceAll(kind, "_", " "),
				WakeID:  str(event["wake_id"]),
				Preview: interfaceEventDetail(event),
			})
		}
	}
	return items
}

func interfaceThoughts(wakes []map[string]any, limit int) []finnInterfaceText {
	items := []finnInterfaceText{}
	start := len(wakes) - limit
	if start < 0 {
		start = 0
	}
	for i := len(wakes) - 1; i >= start; i-- {
		wakeID := str(wakes[i]["wake_id"])
		textOutputs := anySlice(wakes[i]["text_outputs"])
		for j := len(textOutputs) - 1; j >= 0; j-- {
			text, _ := textOutputs[j].(map[string]any)
			preview := compactOneLine(str(text["preview"]), 420)
			if preview == "" {
				continue
			}
			items = append(items, finnInterfaceText{
				Source:    "wake thought",
				WakeID:    wakeID,
				Preview:   preview,
				Bytes:     number(text["bytes"]),
				Truncated: boolValue(text["truncated"]),
			})
			if len(items) >= 10 {
				return items
			}
		}
	}
	return items
}

func interfaceCreations(wakes []map[string]any, limit int) []finnInterfaceCreation {
	items := []finnInterfaceCreation{}
	start := len(wakes) - limit
	if start < 0 {
		start = 0
	}
	for i := len(wakes) - 1; i >= start; i-- {
		wakeID := str(wakes[i]["wake_id"])
		for _, raw := range reverseAny(anySlice(wakes[i]["tool_calls"])) {
			call, _ := raw.(map[string]any)
			name := str(call["name"])
			if !isCreationTool(name) {
				continue
			}
			result, _ := call["result"].(map[string]any)
			path := str(result["path"])
			if path == "" {
				path = argumentPath(call["arguments"])
			}
			detail := creationDetail(call)
			status := "unknown"
			if len(result) > 0 {
				if boolValue(result["ok"]) {
					status = "ok"
				} else {
					status = "not ok"
				}
			}
			items = append(items, finnInterfaceCreation{
				Kind:   name,
				Name:   creationName(name, path, call),
				Path:   path,
				WakeID: wakeID,
				Detail: detail,
				Status: status,
			})
			if len(items) >= 18 {
				return items
			}
		}
	}
	return items
}

func creationDetail(call map[string]any) string {
	args, _ := call["arguments"].(map[string]any)
	result, _ := call["result"].(map[string]any)
	for _, key := range []string{"command", "script", "content"} {
		if value := compactOneLine(str(args[key]), 280); value != "" {
			return value
		}
	}
	if output := toolOutputPreview(call); output != "" {
		return output
	}
	if errText := compactOneLine(str(result["error"]), 280); errText != "" {
		return errText
	}
	return compactOneLine(compactJSON(args), 280)
}

func creationName(tool string, path string, call map[string]any) string {
	if path != "" {
		return filepath.Base(path)
	}
	if tool != "" {
		return strings.ReplaceAll(tool, "_", " ")
	}
	return fmt.Sprintf("tool #%v", call["index"])
}

func isCreationTool(name string) bool {
	switch name {
	case "shell", "run_script", "write_file", "append_file":
		return true
	default:
		return false
	}
}

func argumentPath(arguments any) string {
	args, _ := arguments.(map[string]any)
	return str(args["path"])
}

func interfaceToolCounts(wakes []map[string]any) []finnInterfaceMetricPair {
	counts := map[string]int{}
	for _, wake := range wakes {
		for _, raw := range anySlice(wake["tool_calls"]) {
			call, _ := raw.(map[string]any)
			name := str(call["name"])
			if name != "" {
				counts[name]++
			}
		}
	}
	names := make([]string, 0, len(counts))
	for name := range counts {
		names = append(names, name)
	}
	sort.Strings(names)
	items := []finnInterfaceMetricPair{}
	for _, name := range names {
		items = append(items, finnInterfaceMetricPair{Name: name, Count: counts[name]})
	}
	return items
}

func interfaceTotals(wakes []map[string]any, events []Event, world finnInterfaceWorld, toolCounts []finnInterfaceMetricPair) finnInterfaceTotals {
	totals := finnInterfaceTotals{Wakes: len(wakes), WorldEntries: world.Count}
	for _, wake := range wakes {
		totals.TextOutputs += lenArray(wake["text_outputs"])
		totals.ModelResponses += lenArray(wake["model_responses"])
		totals.ToolCalls += lenArray(wake["tool_calls"])
		totals.Errors += lenArray(wake["errors"])
		if diff, ok := wake["diff_summary"].(map[string]any); ok && boolValue(diff["changed"]) {
			totals.ProductiveWakes++
		}
	}
	for _, item := range toolCounts {
		if isCreationTool(item.Name) {
			totals.WorldMutations += item.Count
		}
	}
	for _, event := range events {
		if str(event["type"]) == "controller_error" {
			totals.Errors++
		}
	}
	return totals
}

func recentInterfaceFieldNotes(cfg Config, limit int) []finnInterfaceNote {
	if limit <= 0 {
		return []finnInterfaceNote{}
	}
	paths, err := filepath.Glob(filepath.Join(cfg.MakerPlace, "field-notes", "*.md"))
	if err != nil {
		return []finnInterfaceNote{}
	}
	sort.Strings(paths)
	start := len(paths) - limit
	if start < 0 {
		start = 0
	}
	notes := []finnInterfaceNote{}
	for i := len(paths) - 1; i >= start; i-- {
		data, err := os.ReadFile(paths[i])
		if err != nil {
			continue
		}
		content := string(data)
		title := filepath.Base(paths[i])
		for _, line := range strings.Split(content, "\n") {
			line = strings.TrimSpace(strings.TrimPrefix(line, "#"))
			if line != "" {
				title = line
				break
			}
		}
		id := strings.TrimSuffix(filepath.Base(paths[i]), filepath.Ext(paths[i]))
		notes = append(notes, finnInterfaceNote{
			ID:      id,
			Path:    paths[i],
			Title:   title,
			Preview: compactOneLine(content, 520),
		})
	}
	return notes
}

func interfaceRecentEvents(events []Event, limit int) []finnInterfaceEvent {
	recent := takeLastEvents(events, limit)
	items := []finnInterfaceEvent{}
	for i := len(recent) - 1; i >= 0; i-- {
		event := recent[i]
		items = append(items, finnInterfaceEvent{
			Time:   str(event["time"]),
			Type:   str(event["type"]),
			WakeID: str(event["wake_id"]),
			Detail: interfaceEventDetail(event),
			Level:  interfaceEventLevel(str(event["type"])),
		})
	}
	return items
}

func interfaceEventDetail(event Event) string {
	switch str(event["type"]) {
	case "model_text":
		payload, _ := event["text"].(map[string]any)
		return compactOneLine(str(payload["preview"]), 180)
	case "tool_call":
		return fmt.Sprintf("%s %s", str(event["tool"]), compactOneLine(compactJSON(event["arguments"]), 180))
	case "model_response":
		return fmt.Sprintf("model=%s finish=%s tool_calls=%v", str(event["model"]), str(event["finish_reason"]), event["tool_call_count"])
	case "wake_end":
		return "reason=" + str(event["end_reason"])
	case "model_error", "controller_error":
		return compactOneLine(str(event["error"]), 180)
	case "world_snapshot_written":
		return fmt.Sprintf("%s snapshot %s", str(event["label"]), str(event["path"]))
	default:
		return compactOneLine(compactJSON(event), 180)
	}
}

func interfaceEventLevel(kind string) string {
	switch kind {
	case "model_error", "controller_error", "tool_call_error":
		return "bad"
	case "required_tool_choice_ignored", "model_text_only", "text_only_limit_reached":
		return "warn"
	case "tool_call", "run_script_result", "write_file_result", "append_file_result", "shell_result":
		return "work"
	case "wake_start", "wake_end", "wake_summary_written", "field_note_written":
		return "good"
	default:
		return "neutral"
	}
}

func extractInterfaceEntities(kind string, worldEntries []string, thoughts []finnInterfaceText, notes []finnInterfaceNote, keywords []string, limit int) []finnInterfaceEntity {
	seen := map[string]bool{}
	entities := []finnInterfaceEntity{}
	add := func(name string, source string, detail string) {
		name = strings.TrimSpace(name)
		if name == "" {
			name = kind
		}
		key := strings.ToLower(name + "|" + source + "|" + detail)
		if seen[key] {
			return
		}
		seen[key] = true
		entities = append(entities, finnInterfaceEntity{
			Name:   name,
			Kind:   kind,
			Source: source,
			Detail: compactOneLine(detail, 220),
		})
	}
	for _, entry := range worldEntries {
		lower := strings.ToLower(entry)
		for _, keyword := range keywords {
			if strings.Contains(lower, keyword) {
				add(filepath.Base(entry), "world", entry)
				break
			}
		}
		if len(entities) >= limit {
			return entities
		}
	}
	for _, thought := range thoughts {
		lower := strings.ToLower(thought.Preview)
		for _, keyword := range keywords {
			if strings.Contains(lower, keyword) {
				add(keyword, "thought "+thought.WakeID, thought.Preview)
				break
			}
		}
		if len(entities) >= limit {
			return entities
		}
	}
	for _, note := range notes {
		lower := strings.ToLower(note.Preview)
		for _, keyword := range keywords {
			if strings.Contains(lower, keyword) {
				add(keyword, "field note "+note.ID, note.Preview)
				break
			}
		}
		if len(entities) >= limit {
			return entities
		}
	}
	return entities
}

func interfacePlaces(worldEntries []string, limit int) []finnInterfaceEntity {
	places := []finnInterfaceEntity{}
	seen := map[string]bool{}
	for _, entry := range worldEntries {
		cleaned := strings.TrimPrefix(strings.TrimPrefix(entry, "./"), "/")
		if cleaned == "" {
			continue
		}
		name := strings.Split(cleaned, "/")[0]
		if strings.Contains(filepath.Base(cleaned), ".") && !strings.Contains(cleaned, "/") {
			continue
		}
		if seen[name] {
			continue
		}
		seen[name] = true
		places = append(places, finnInterfaceEntity{
			Name:   name,
			Kind:   "place",
			Source: "world",
			Detail: entry,
		})
		if len(places) >= limit {
			break
		}
	}
	return places
}

func interfaceHealth(label string, eventsErr error, wakesErr error, latestWake finnInterfaceWake, totals finnInterfaceTotals) []finnInterfaceSignal {
	items := []finnInterfaceSignal{}
	items = append(items, finnInterfaceSignal{Label: "runtime", Detail: label, Level: strings.ToLower(label)})
	if eventsErr != nil && !errors.Is(eventsErr, os.ErrNotExist) {
		items = append(items, finnInterfaceSignal{Label: "events", Detail: eventsErr.Error(), Level: "bad"})
	}
	if wakesErr != nil {
		items = append(items, finnInterfaceSignal{Label: "wakes", Detail: wakesErr.Error(), Level: "bad"})
	}
	if latestWake.Present {
		level := latestWake.StateClass
		items = append(items, finnInterfaceSignal{Label: "latest wake", Detail: latestWake.Assessment, Level: level})
	}
	if totals.Errors > 0 {
		items = append(items, finnInterfaceSignal{Label: "errors", Detail: fmt.Sprintf("%d recorded", totals.Errors), Level: "bad"})
	}
	if totals.WorldMutations > 0 {
		items = append(items, finnInterfaceSignal{Label: "world mutations", Detail: fmt.Sprintf("%d creation-capable calls", totals.WorldMutations), Level: "good"})
	}
	return items
}

func inspectInterfaceWorld(cfg Config, maxDepth int) finnInterfaceWorld {
	if err := dockerRun("volume", "create", cfg.WorldVolume); err != nil {
		return finnInterfaceWorld{OK: false, Error: err.Error()}
	}
	if err := dockerRun("image", "inspect", cfg.SandboxImage); err != nil {
		return finnInterfaceWorld{OK: false, Error: err.Error()}
	}
	script := fmt.Sprintf("cd /world && if [ -z \"$(find . -mindepth 1 -maxdepth 1 -print -quit)\" ]; then echo \"(empty)\"; else find . -mindepth 1 -maxdepth %d -print | sort; fi", maxDepth)
	output, err := dockerOutput("run", "--rm", "-v", cfg.WorldVolume+":/world:ro", cfg.SandboxImage, "bash", "-lc", script)
	if err != nil {
		return finnInterfaceWorld{OK: false, Error: err.Error()}
	}
	entries := []string{}
	for _, line := range strings.Split(strings.TrimSpace(output), "\n") {
		line = strings.TrimSpace(line)
		if line != "" && line != "(empty)" {
			entries = append(entries, line)
		}
	}
	return finnInterfaceWorld{OK: true, Entries: entries, Count: len(entries)}
}

func publishFinnInterfaceSnapshot(cfg Config, notePath string, snapshot finnInterfaceSnapshot) error {
	cleaned, err := cleanWorldRelativePath(notePath)
	if err != nil {
		return err
	}
	if err := dockerRun("volume", "create", cfg.WorldVolume); err != nil {
		return err
	}
	if err := dockerRun("image", "inspect", cfg.SandboxImage); err != nil {
		return err
	}
	content := renderFinnInterfaceWorldNote(snapshot)
	target := "/world/" + cleaned
	script := fmt.Sprintf("set -euo pipefail\nmkdir -p %s\ncat > %s\n", shellQuote(filepath.Dir(target)), shellQuote(target))
	cmd := exec.Command("docker", "run", "--rm", "-i", "-v", cfg.WorldVolume+":/world", cfg.SandboxImage, "bash", "-lc", script)
	cmd.Stdin = strings.NewReader(content)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = err.Error()
		}
		return errors.New(detail)
	}
	return nil
}

func cleanWorldRelativePath(path string) (string, error) {
	path = strings.TrimSpace(path)
	path = strings.TrimPrefix(path, "/world/")
	if path == "" {
		return "", errors.New("world note path is empty")
	}
	if strings.Contains(path, "\x00") || strings.Contains(path, "\n") {
		return "", errors.New("world note path contains invalid characters")
	}
	if filepath.IsAbs(path) {
		return "", errors.New("world note path must be relative to /world")
	}
	cleaned := filepath.Clean(path)
	if cleaned == "." || cleaned == ".." || strings.HasPrefix(cleaned, "../") {
		return "", errors.New("world note path must stay inside /world")
	}
	return cleaned, nil
}

func renderFinnInterfaceWorldNote(snapshot finnInterfaceSnapshot) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Finn Interface Status\n\n")
	fmt.Fprintf(&b, "Generated: %s\n", snapshot.GeneratedAt)
	fmt.Fprintf(&b, "Runtime: %s - %s\n", snapshot.Runtime.Label, snapshot.Runtime.Detail)
	if snapshot.LatestWake.Present {
		fmt.Fprintf(&b, "Latest wake: %s\n", snapshot.LatestWake.ID)
		fmt.Fprintf(&b, "Latest assessment: %s\n", snapshot.LatestWake.Assessment)
	}
	fmt.Fprintf(&b, "\n## Signals\n\n")
	for _, signal := range snapshot.Health {
		fmt.Fprintf(&b, "- %s: %s\n", signal.Label, signal.Detail)
	}
	fmt.Fprintf(&b, "\n## Recent Thoughts\n\n")
	if len(snapshot.Thoughts) == 0 {
		fmt.Fprintf(&b, "- No recorded thoughts yet.\n")
	}
	for _, thought := range snapshot.Thoughts {
		fmt.Fprintf(&b, "- %s: %s\n", thought.WakeID, thought.Preview)
	}
	fmt.Fprintf(&b, "\n## Recent Creations\n\n")
	if len(snapshot.Creations) == 0 {
		fmt.Fprintf(&b, "- No creation-capable tool calls are visible yet.\n")
	}
	for _, creation := range snapshot.Creations {
		fmt.Fprintf(&b, "- %s %s", creation.Kind, creation.Name)
		if creation.Path != "" {
			fmt.Fprintf(&b, " path=%s", creation.Path)
		}
		fmt.Fprintf(&b, " status=%s wake=%s\n", creation.Status, creation.WakeID)
	}
	fmt.Fprintf(&b, "\n## Inhabitants Seen By The Interface\n\n")
	if len(snapshot.Friends) == 0 {
		fmt.Fprintf(&b, "- Friends: none named yet.\n")
	} else {
		for _, friend := range snapshot.Friends {
			fmt.Fprintf(&b, "- Friend %s from %s: %s\n", friend.Name, friend.Source, friend.Detail)
		}
	}
	if len(snapshot.Creatures) == 0 {
		fmt.Fprintf(&b, "- Creatures: none named yet.\n")
	} else {
		for _, creature := range snapshot.Creatures {
			fmt.Fprintf(&b, "- Creature %s from %s: %s\n", creature.Name, creature.Source, creature.Detail)
		}
	}
	fmt.Fprintf(&b, "\n## World Entries\n\n")
	if len(snapshot.World.Entries) == 0 {
		fmt.Fprintf(&b, "- No world entries available through the interface.\n")
	}
	for _, entry := range snapshot.World.Entries {
		fmt.Fprintf(&b, "- %s\n", entry)
	}
	return b.String()
}

func renderFinnInterfaceHTML(snapshot finnInterfaceSnapshot) (string, error) {
	tmpl, err := template.New("finn-interface").Funcs(template.FuncMap{
		"class": interfaceClass,
	}).Parse(finnInterfaceHTMLTemplate)
	if err != nil {
		return "", err
	}
	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, snapshot); err != nil {
		return "", err
	}
	return buf.String(), nil
}

func interfaceClass(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	if value == "" {
		return "neutral"
	}
	var b strings.Builder
	for _, ch := range value {
		if (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') {
			b.WriteRune(ch)
		} else if ch == '-' || ch == '_' || ch == ' ' {
			b.WriteByte('-')
		}
	}
	result := strings.Trim(b.String(), "-")
	if result == "" {
		return "neutral"
	}
	return result
}

func anySlice(value any) []any {
	items, ok := value.([]any)
	if !ok {
		return []any{}
	}
	return items
}

func reverseAny(items []any) []any {
	reversed := make([]any, len(items))
	for i := range items {
		reversed[len(items)-1-i] = items[i]
	}
	return reversed
}

func shellQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "'\"'\"'") + "'"
}

const finnInterfaceHTMLTemplate = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {{if gt .RefreshSeconds 0}}<meta http-equiv="refresh" content="{{.RefreshSeconds}}">{{end}}
  <title>Finn Interface</title>
  <style>
    :root {
      --paper: #eee8dc;
      --panel: #fbf8ef;
      --ink: #18201d;
      --muted: #65706a;
      --line: #c8bcaa;
      --copper: #b65f3d;
      --teal: #1f7a83;
      --violet: #4d456f;
      --moss: #4c7c3f;
      --signal: #d6e15f;
      --bad: #a63f35;
      --shadow: rgba(24, 32, 29, 0.12);
    }
    * { box-sizing: border-box; }
    html { background: var(--paper); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; min-width: 320px; }
    .shell { width: min(1760px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 42px; }
    .topbar { display: grid; grid-template-columns: minmax(280px, 1fr) auto; gap: 18px; align-items: end; border-bottom: 2px solid var(--ink); padding-bottom: 18px; }
    h1 { margin: 0; font-family: Georgia, "Times New Roman", serif; font-size: clamp(2.4rem, 6vw, 6.7rem); line-height: .82; font-weight: 700; letter-spacing: 0; }
    .subtitle { margin: 12px 0 0; max-width: 860px; color: var(--muted); font-size: 1rem; line-height: 1.45; }
    .stamp { justify-self: end; text-align: right; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .78rem; color: var(--muted); }
    .badge { display: inline-flex; align-items: center; min-height: 32px; padding: 0 10px; border: 1px solid var(--ink); border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .78rem; text-transform: uppercase; background: var(--signal); color: var(--ink); }
    .badge.idle { background: var(--panel); }
    .badge.awake, .badge.waiting { background: var(--signal); }
    .badge.active { background: #b7e0e3; }
    .metrics { display: grid; grid-template-columns: repeat(7, minmax(120px, 1fr)); gap: 1px; border: 1px solid var(--ink); margin-top: 18px; background: var(--ink); }
    .metric { min-height: 92px; padding: 12px; background: var(--panel); }
    .metric strong { display: block; font-family: Georgia, "Times New Roman", serif; font-size: clamp(1.8rem, 4vw, 3.1rem); line-height: .9; }
    .metric span { display: block; margin-top: 10px; color: var(--muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .08em; }
    .grid { display: grid; grid-template-columns: 1.35fr .9fr .9fr; gap: 16px; margin-top: 16px; align-items: start; }
    .panel { background: var(--panel); border: 1px solid var(--ink); box-shadow: 4px 4px 0 var(--shadow); }
    .panel.wide { grid-column: span 2; }
    .panel.full { grid-column: 1 / -1; }
    .panel header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 12px 14px; }
    .panel h2 { margin: 0; font-size: .86rem; letter-spacing: .09em; text-transform: uppercase; }
    .panel .kicker { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .73rem; white-space: nowrap; }
    .body { padding: 14px; }
    .scroll-panel .body { max-height: 620px; overflow: auto; }
    .status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; }
    .kv { min-width: 0; border-bottom: 1px solid var(--line); padding-bottom: 7px; }
    .kv span { display: block; color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; }
    .kv strong { display: block; margin-top: 4px; overflow-wrap: anywhere; font-size: .94rem; }
    .latest { display: grid; grid-template-columns: 170px 1fr; gap: 14px; align-items: stretch; }
    .wakeplate { display: flex; flex-direction: column; justify-content: space-between; min-height: 180px; padding: 14px; background: var(--ink); color: var(--panel); }
    .wakeplate .id { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .85rem; }
    .wakeplate .duration { font-family: Georgia, "Times New Roman", serif; font-size: 2.4rem; line-height: .95; color: var(--signal); }
    .assessment { margin: 0 0 12px; font-size: 1.15rem; line-height: 1.35; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip { border: 1px solid var(--line); border-radius: 999px; padding: 4px 8px; background: #fffdf6; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .72rem; }
    .stream { display: grid; gap: 10px; }
    .thought { border-left: 4px solid var(--teal); padding: 9px 0 9px 12px; }
    .thought p, .creation p, .entity p, .note p, .event p { margin: 4px 0 0; line-height: 1.42; overflow-wrap: anywhere; }
    .meta { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .72rem; }
    .creation { display: grid; grid-template-columns: 86px 1fr; gap: 10px; border-top: 1px solid var(--line); padding: 10px 0; }
    .creation:first-child { border-top: 0; padding-top: 0; }
    .tool { align-self: start; border: 1px solid var(--ink); border-radius: 4px; padding: 4px 6px; text-align: center; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .7rem; background: #e8f2f1; }
    .entity-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .entity { border-top: 3px solid var(--violet); background: #fffdf6; padding: 10px; min-height: 98px; }
    .entity strong { display: block; overflow-wrap: anywhere; }
    .world-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; max-height: 420px; overflow: auto; }
    .world-list code { display: block; border: 1px solid var(--line); background: #fffdf6; padding: 7px; overflow-wrap: anywhere; white-space: normal; font-size: .76rem; }
    .wake-table, .event-table { width: 100%; border-collapse: collapse; font-size: .85rem; }
    .wake-table th, .wake-table td, .event-table th, .event-table td { border-bottom: 1px solid var(--line); padding: 8px 7px; text-align: left; vertical-align: top; }
    .wake-table th, .event-table th { color: var(--muted); font-size: .7rem; text-transform: uppercase; letter-spacing: .07em; }
    .state-good { color: var(--moss); }
    .state-bad { color: var(--bad); }
    .state-warn { color: var(--copper); }
    .state-work { color: var(--teal); }
    .event { border-left: 4px solid var(--line); padding-left: 10px; margin-bottom: 9px; }
    .event.good { border-color: var(--moss); }
    .event.bad { border-color: var(--bad); }
    .event.warn { border-color: var(--copper); }
    .event.work { border-color: var(--teal); }
    .health { display: flex; flex-wrap: wrap; gap: 8px; }
    .signal { border: 1px solid var(--line); background: #fffdf6; padding: 8px 10px; min-width: 170px; }
    .signal strong { display: block; text-transform: uppercase; letter-spacing: .07em; font-size: .7rem; }
    .empty { margin: 0; color: var(--muted); font-style: italic; }
    @media (max-width: 1180px) {
      .grid { grid-template-columns: 1fr 1fr; }
      .panel.wide { grid-column: span 2; }
      .metrics { grid-template-columns: repeat(4, minmax(120px, 1fr)); }
      .world-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
      .shell { width: min(100vw - 20px, 760px); padding-top: 12px; }
      .topbar { grid-template-columns: 1fr; }
      .stamp { justify-self: start; text-align: left; }
      .metrics, .grid, .latest, .entity-grid, .status-grid, .world-list { grid-template-columns: 1fr; }
      .panel.wide { grid-column: auto; }
      .creation { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="topbar">
      <div>
        <span class="badge {{.Runtime.Class}}">{{.Runtime.Label}}</span>
        <h1>Finn Interface</h1>
        <p class="subtitle">A live Maker Place reading room for Finn's thoughts, creations, world mutations, named inhabitants, field notes, and controller health.</p>
      </div>
      <div class="stamp">
        <div>generated {{.GeneratedAt}}</div>
        <div>maker place {{.MakerPlace}}</div>
        {{if .WorldNotePublished}}<div>published /world/{{.WorldNotePath}}</div>{{end}}
        {{if .WorldNoteError}}<div>publish error {{.WorldNoteError}}</div>{{end}}
      </div>
    </section>

    <section class="metrics" aria-label="Runtime totals">
      <div class="metric"><strong>{{.Totals.Wakes}}</strong><span>wakes</span></div>
      <div class="metric"><strong>{{.Totals.ProductiveWakes}}</strong><span>world-changing wakes</span></div>
      <div class="metric"><strong>{{.Totals.ModelResponses}}</strong><span>model responses</span></div>
      <div class="metric"><strong>{{.Totals.TextOutputs}}</strong><span>thought records</span></div>
      <div class="metric"><strong>{{.Totals.ToolCalls}}</strong><span>tool calls</span></div>
      <div class="metric"><strong>{{.Totals.WorldMutations}}</strong><span>creation-capable acts</span></div>
      <div class="metric"><strong>{{.Totals.WorldEntries}}</strong><span>world entries</span></div>
    </section>

    <section class="grid">
      <article class="panel wide">
        <header><h2>Current Wake</h2><span class="kicker">{{.Runtime.Detail}}</span></header>
        <div class="body">
          {{if .LatestWake.Present}}
          <div class="latest">
            <div class="wakeplate">
              <div class="id">{{.LatestWake.ID}}</div>
              <div class="duration">{{.LatestWake.Duration}}</div>
              <div>{{.LatestWake.Reason}}</div>
            </div>
            <div>
              <p class="assessment {{printf "state-%s" .LatestWake.StateClass}}">{{.LatestWake.Assessment}}</p>
              <div class="status-grid">
                <div class="kv"><span>model</span><strong>{{.LatestWake.Model}}</strong></div>
                <div class="kv"><span>started</span><strong>{{.LatestWake.Started}}</strong></div>
                <div class="kv"><span>ended</span><strong>{{.LatestWake.Ended}}</strong></div>
                <div class="kv"><span>activity</span><strong>{{.LatestWake.ModelResponses}} responses, {{.LatestWake.ToolCount}} tools, {{.LatestWake.TextCount}} texts</strong></div>
              </div>
              <div class="chips" style="margin-top:12px">
                {{range .LatestWake.ToolSequence}}<span class="chip">{{.}}</span>{{else}}<span class="chip">no tools recorded</span>{{end}}
              </div>
            </div>
          </div>
          {{else}}<p class="empty">{{.LatestWake.Assessment}}</p>{{end}}
        </div>
      </article>

      <article class="panel">
        <header><h2>Runtime</h2><span class="kicker">controller</span></header>
        <div class="body status-grid">
          <div class="kv"><span>controller</span><strong>{{.Runtime.Controller}}</strong></div>
          <div class="kv"><span>wake lock</span><strong>{{.Runtime.WakeLock}}</strong></div>
          <div class="kv"><span>sandbox</span><strong>{{.Runtime.Sandbox}}</strong></div>
          <div class="kv"><span>latest event</span><strong>{{.Runtime.LatestEvent}}</strong></div>
        </div>
      </article>

      <article class="panel">
        <header><h2>Thinking</h2><span class="kicker">current trace</span></header>
        <div class="body stream">
          {{range .Thinking}}<div class="thought"><span class="meta">{{.Source}} {{.WakeID}}</span><p>{{.Preview}}</p></div>{{else}}<p class="empty">No current thinking trace is available yet.</p>{{end}}
        </div>
      </article>

      <article class="panel scroll-panel">
        <header><h2>Thoughts</h2><span class="kicker">recent text</span></header>
        <div class="body stream">
          {{range .Thoughts}}<div class="thought"><span class="meta">{{.WakeID}} {{.Bytes}} bytes</span><p>{{.Preview}}</p></div>{{else}}<p class="empty">Finn has not left text thoughts in recent wakes.</p>{{end}}
        </div>
      </article>

      <article class="panel wide scroll-panel">
        <header><h2>Creations</h2><span class="kicker">files, scripts, shell acts</span></header>
        <div class="body">
          {{range .Creations}}
          <div class="creation">
            <div class="tool">{{.Kind}}<br>{{.Status}}</div>
            <div><strong>{{.Name}}</strong><div class="meta">{{.WakeID}} {{.Path}}</div><p>{{.Detail}}</p></div>
          </div>
          {{else}}<p class="empty">No creation-capable tool calls are visible yet.</p>{{end}}
        </div>
      </article>

      <article class="panel">
        <header><h2>Inhabitants</h2><span class="kicker">friends and creatures</span></header>
        <div class="body entity-grid">
          <div>
            <h3 class="meta">Friends</h3>
            {{range .Friends}}<div class="entity"><strong>{{.Name}}</strong><span class="meta">{{.Source}}</span><p>{{.Detail}}</p></div>{{else}}<p class="empty">No named friends found yet.</p>{{end}}
          </div>
          <div>
            <h3 class="meta">Creatures</h3>
            {{range .Creatures}}<div class="entity"><strong>{{.Name}}</strong><span class="meta">{{.Source}}</span><p>{{.Detail}}</p></div>{{else}}<p class="empty">No named creatures found yet.</p>{{end}}
          </div>
        </div>
      </article>

      <article class="panel">
        <header><h2>Places</h2><span class="kicker">world names</span></header>
        <div class="body stream">
          {{range .Places}}<div class="entity"><strong>{{.Name}}</strong><span class="meta">{{.Source}}</span><p>{{.Detail}}</p></div>{{else}}<p class="empty">No place-like world entries found yet.</p>{{end}}
        </div>
      </article>

      <article class="panel wide">
        <header><h2>World Surface</h2><span class="kicker">{{.World.Count}} entries</span></header>
        <div class="body">
          {{if .World.OK}}
          <div class="world-list">{{range .World.Entries}}<code>{{.}}</code>{{else}}<p class="empty">The world volume is empty.</p>{{end}}</div>
          {{else}}<p class="empty">{{.World.Error}}</p>{{end}}
        </div>
      </article>

      <article class="panel scroll-panel">
        <header><h2>Field Notes</h2><span class="kicker">observer record</span></header>
        <div class="body stream">
          {{range .FieldNotes}}<div class="note"><span class="meta">{{.ID}}</span><p><strong>{{.Title}}</strong></p><p>{{.Preview}}</p></div>{{else}}<p class="empty">No field notes written yet.</p>{{end}}
        </div>
      </article>

      <article class="panel wide">
        <header><h2>Recent Wakes</h2><span class="kicker">newest first</span></header>
        <div class="body">
          <table class="wake-table">
            <thead><tr><th>wake</th><th>duration</th><th>reason</th><th>model</th><th>tools</th><th>world</th></tr></thead>
            <tbody>
            {{range .RecentWakes}}<tr><td>{{.ID}}</td><td>{{.Duration}}</td><td class="{{printf "state-%s" .StateClass}}">{{.Reason}}</td><td>{{.Model}}</td><td>{{.ToolCount}}</td><td>{{.WorldChanged}}</td></tr>{{else}}<tr><td colspan="6">No wakes found.</td></tr>{{end}}
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel">
        <header><h2>Health</h2><span class="kicker">signals</span></header>
        <div class="body health">
          {{range .Health}}<div class="signal {{.Level}}"><strong>{{.Label}}</strong><span>{{.Detail}}</span></div>{{else}}<p class="empty">No health signals available.</p>{{end}}
        </div>
      </article>

      <article class="panel full">
        <header><h2>Event Stream</h2><span class="kicker">latest first</span></header>
        <div class="body">
          {{range .RecentEvents}}<div class="event {{.Level}}"><span class="meta">{{.Time}} {{.Type}} wake={{.WakeID}}</span><p>{{.Detail}}</p></div>{{else}}<p class="empty">No events found.</p>{{end}}
        </div>
      </article>
    </section>
  </main>
</body>
</html>
`
