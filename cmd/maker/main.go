package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
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

type Config struct {
	MakerPlace   string
	WorldVolume  string
	SandboxImage string
	InputPath    string
	OutputPath   string
	JSON         bool
}

type Event map[string]any

func main() {
	if err := run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func run(args []string, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
	dotenv := readDotenv(".env")
	cfg := Config{
		MakerPlace:   valueFromEnv("MAKER_PLACE_DIR", dotenv, "maker-place"),
		WorldVolume:  valueFromEnv("WORLD_VOLUME", dotenv, "maker_finn_world"),
		SandboxImage: valueFromEnv("SANDBOX_IMAGE", dotenv, "maker-finn-sandbox:latest"),
	}

	global := flag.NewFlagSet("maker", flag.ContinueOnError)
	global.SetOutput(stderr)
	global.StringVar(&cfg.MakerPlace, "maker-place", cfg.MakerPlace, "Maker Place directory")
	global.StringVar(&cfg.WorldVolume, "world-volume", cfg.WorldVolume, "Docker volume mounted at /world")
	global.StringVar(&cfg.SandboxImage, "sandbox-image", cfg.SandboxImage, "sandbox image used for world inspection")
	global.StringVar(&cfg.InputPath, "input", "", "read command input from file, or '-' for stdin")
	global.StringVar(&cfg.OutputPath, "output", "", "write command output to file, or '-' for stdout")
	global.BoolVar(&cfg.JSON, "json", false, "write JSON output")
	if err := global.Parse(args); err != nil {
		return err
	}
	rest := global.Args()
	if len(rest) == 0 {
		printUsage(stdout)
		return nil
	}

	cmd := rest[0]
	cmdArgs := rest[1:]
	if cmd == "dashboard" || cmd == "watch" {
		out, closeOut, err := openOutputWriter(cfg.OutputPath, stdout)
		if err != nil {
			return err
		}
		defer closeOut()
		return cmdDashboard(cfg, cmdArgs, stdin, out)
	}

	var out bytes.Buffer
	var err error
	switch cmd {
	case "status":
		err = cmdStatus(cfg, &out)
	case "events":
		err = cmdEvents(cfg, cmdArgs, stdin, &out)
	case "wakes":
		err = cmdWakes(cfg, &out)
	case "show":
		err = cmdShow(cfg, cmdArgs, stdin, &out)
	case "world":
		err = cmdWorld(cfg, cmdArgs, &out)
	case "doctor":
		err = cmdDoctor(cfg, &out)
	case "probe-model":
		err = cmdProbeModel(cfg, cmdArgs, &out)
	case "count-model-responses":
		err = cmdCountModelResponses(cfg, cmdArgs, stdin, &out)
	case "evaluate":
		err = cmdEvaluate(cfg, cmdArgs, stdin, &out)
	case "dashboard", "watch":
		err = cmdDashboard(cfg, cmdArgs, stdin, &out)
	case "help", "-h", "--help":
		printUsage(&out)
	default:
		err = fmt.Errorf("unknown command: %s", cmd)
	}
	if err != nil {
		return err
	}
	return writeOutput(cfg.OutputPath, out.Bytes(), stdout)
}

func printUsage(w io.Writer) {
	fmt.Fprintln(w, "usage: maker [global flags] COMMAND [command flags]")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "global flags:")
	fmt.Fprintln(w, "  --maker-place PATH   Maker Place directory")
	fmt.Fprintln(w, "  --world-volume NAME  Docker world volume")
	fmt.Fprintln(w, "  --sandbox-image IMG  sandbox image for world inspection")
	fmt.Fprintln(w, "  --input FILE|-       read command input from file/stdin where supported")
	fmt.Fprintln(w, "  --output FILE|-      write normal output to file/stdout")
	fmt.Fprintln(w, "  --json               emit JSON where supported")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "commands:")
	fmt.Fprintln(w, "  status")
	fmt.Fprintln(w, "  events --last 20")
	fmt.Fprintln(w, "  wakes")
	fmt.Fprintln(w, "  show [WAKE_ID|last]")
	fmt.Fprintln(w, "  world --max-depth 5")
	fmt.Fprintln(w, "  doctor")
	fmt.Fprintln(w, "  probe-model --provider ollama --model llama3.1:8b")
	fmt.Fprintln(w, "  count-model-responses [--wake current|last|WAKE_ID]")
	fmt.Fprintln(w, "  evaluate [--wake current|last|WAKE_ID] [--last-responses 10]")
	fmt.Fprintln(w, "  dashboard [--interval 10] [--events 8] [--last-responses 10]")
}

func cmdStatus(cfg Config, out io.Writer) error {
	lock, _ := readJSONFile(filepath.Join(cfg.MakerPlace, "wake.lock"))
	pidInfo := readPID(filepath.Join(cfg.MakerPlace, "controller.pid"))
	containers := dockerLines("ps", "--format", "{{.Names}}\t{{.Status}}", "--filter", "label=maker.runtime=finn")
	latestEvent, _ := latestEvent(defaultEventsPath(cfg))
	latestWake, _ := latestWakeSummary(cfg)

	if cfg.JSON {
		payload := map[string]any{
			"maker_place":       cfg.MakerPlace,
			"controller_pid":    pidInfo,
			"wake_lock":         lock,
			"active_containers": containers,
			"latest_event":      latestEvent,
			"latest_wake":       latestWake,
		}
		return writeJSON(out, payload)
	}

	fmt.Fprintf(out, "maker-place: %s\n", cfg.MakerPlace)
	fmt.Fprintf(out, "controller pid: %s\n", pidInfoText(pidInfo))
	if len(lock) == 0 {
		fmt.Fprintln(out, "wake lock: none")
	} else {
		fmt.Fprintf(out, "wake lock: wake_id=%v pid=%v started_at=%v\n", lock["wake_id"], lock["pid"], lock["started_at"])
	}
	if len(containers) == 0 {
		fmt.Fprintln(out, "active sandbox: none")
	} else {
		fmt.Fprintln(out, "active sandbox:")
		for _, line := range containers {
			fmt.Fprintf(out, "  %s\n", line)
		}
	}
	if latestEvent != nil {
		fmt.Fprintf(out, "latest event: %s %s wake=%v\n", str(latestEvent["time"]), str(latestEvent["type"]), latestEvent["wake_id"])
	}
	if latestWake != nil {
		fmt.Fprintf(out, "latest wake: %s reason=%s tools=%d text=%d\n", str(latestWake["wake_id"]), str(latestWake["end_reason"]), lenArray(latestWake["tool_calls"]), lenArray(latestWake["text_outputs"]))
	}
	return nil
}

func cmdEvents(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	fs := flag.NewFlagSet("events", flag.ContinueOnError)
	last := fs.Int("last", 20, "number of recent events")
	if err := fs.Parse(args); err != nil {
		return err
	}
	lines, err := readEventLines(cfg, stdin)
	if err != nil {
		return err
	}
	lines = takeLast(lines, *last)
	if cfg.JSON {
		for _, line := range lines {
			fmt.Fprintln(out, line)
		}
		return nil
	}
	for _, line := range lines {
		event, err := parseEventLine(line)
		if err != nil {
			fmt.Fprintf(out, "invalid: %s\n", line)
			continue
		}
		fmt.Fprintln(out, formatEvent(event))
	}
	return nil
}

func cmdWakes(cfg Config, out io.Writer) error {
	wakes, err := loadWakeSummaries(cfg)
	if err != nil {
		return err
	}
	if cfg.JSON {
		return writeJSON(out, wakes)
	}
	if len(wakes) == 0 {
		fmt.Fprintln(out, "no wakes found")
		return nil
	}
	for _, wake := range wakes {
		fmt.Fprintf(out, "%s  start=%s  end=%s  reason=%s  tools=%d  text=%d\n",
			str(wake["wake_id"]),
			str(wake["start_time"]),
			str(wake["end_time"]),
			str(wake["end_reason"]),
			lenArray(wake["tool_calls"]),
			lenArray(wake["text_outputs"]),
		)
	}
	return nil
}

func cmdShow(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	wakeID := "last"
	if len(args) > 0 {
		wakeID = args[0]
	}
	var wake map[string]any
	var err error
	if cfg.InputPath != "" {
		wake, err = readJSONInput(cfg.InputPath, stdin)
	} else {
		wake, err = loadWake(cfg, wakeID)
	}
	if err != nil {
		return err
	}
	if cfg.JSON {
		return writeJSON(out, wake)
	}
	fmt.Fprintf(out, "wake: %s\n", str(wake["wake_id"]))
	fmt.Fprintf(out, "model: %s\n", str(wake["model"]))
	fmt.Fprintf(out, "start: %s\n", str(wake["start_time"]))
	fmt.Fprintf(out, "end: %s\n", str(wake["end_time"]))
	fmt.Fprintf(out, "reason: %s\n", str(wake["end_reason"]))
	fmt.Fprintf(out, "text outputs: %d\n", lenArray(wake["text_outputs"]))
	fmt.Fprintf(out, "model responses: %d\n", lenArray(wake["model_responses"]))
	toolCalls, _ := wake["tool_calls"].([]any)
	fmt.Fprintf(out, "tools: %d\n", len(toolCalls))
	for _, item := range takeLastAny(toolCalls, 10) {
		call, _ := item.(map[string]any)
		fmt.Fprintf(out, "- #%v %s: %s\n", call["index"], str(call["name"]), compactJSON(call["arguments"]))
	}
	errorsList, _ := wake["errors"].([]any)
	if len(errorsList) > 0 {
		fmt.Fprintln(out, "errors:")
		for _, item := range errorsList {
			fmt.Fprintf(out, "- %v\n", item)
		}
	}
	return nil
}

func cmdWorld(cfg Config, args []string, out io.Writer) error {
	fs := flag.NewFlagSet("world", flag.ContinueOnError)
	maxDepth := fs.Int("max-depth", 5, "maximum find depth")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if err := dockerRun("volume", "create", cfg.WorldVolume); err != nil {
		return err
	}
	if err := dockerRun("image", "inspect", cfg.SandboxImage); err != nil {
		return fmt.Errorf("sandbox image not found: %s; build it with docker build -f Dockerfile.sandbox -t %s .", cfg.SandboxImage, cfg.SandboxImage)
	}
	script := fmt.Sprintf("cd /world && if [ -z \"$(find . -mindepth 1 -maxdepth 1 -print -quit)\" ]; then echo \"(empty)\"; else find . -mindepth 1 -maxdepth %d -print | sort; fi", *maxDepth)
	output, err := dockerOutput("run", "--rm", "-v", cfg.WorldVolume+":/world:ro", cfg.SandboxImage, "bash", "-lc", script)
	if err != nil {
		return err
	}
	if cfg.JSON {
		lines := strings.Split(strings.TrimSpace(output), "\n")
		if strings.TrimSpace(output) == "" {
			lines = []string{}
		}
		return writeJSON(out, map[string]any{"world_volume": cfg.WorldVolume, "entries": lines})
	}
	fmt.Fprint(out, output)
	return nil
}

func cmdDoctor(cfg Config, out io.Writer) error {
	dotenv := readDotenv(".env")
	checks := []map[string]any{}
	add := func(name string, ok bool, detail string) {
		checks = append(checks, map[string]any{"name": name, "ok": ok, "detail": detail})
	}
	_, err := exec.LookPath("docker")
	add("docker_cli", err == nil, errText(err, "found"))
	_, err = dockerOutput("info", "--format", "{{.ServerVersion}}")
	add("docker_daemon", err == nil, errText(err, "reachable"))
	err = dockerRun("image", "inspect", cfg.SandboxImage)
	add("sandbox_image", err == nil, errText(err, cfg.SandboxImage))
	err = dockerRun("volume", "inspect", cfg.WorldVolume)
	add("world_volume", err == nil, errText(err, cfg.WorldVolume))
	add("maker_place_dir", pathExists(cfg.MakerPlace), cfg.MakerPlace)
	add("events_jsonl", pathExists(defaultEventsPath(cfg)), defaultEventsPath(cfg))
	add("wakes_dir", pathExists(filepath.Join(cfg.MakerPlace, "wakes")), filepath.Join(cfg.MakerPlace, "wakes"))
	keyPresent := os.Getenv("OPENROUTER_API_KEY") != "" || dotenv["OPENROUTER_API_KEY"] != ""
	add("openrouter_key_present", keyPresent, "OPENROUTER_API_KEY")
	ollamaBaseURL := valueFromEnv("OLLAMA_BASE_URL", dotenv, "http://localhost:11434")
	ollamaPrimary := valueFromEnv("OLLAMA_MODEL", dotenv, "llama3.1:8b")
	ollamaFallbacks := splitCSV(valueFromEnv("OLLAMA_FALLBACKS", dotenv, "qwen3.5:9b"))
	ollamaModels, err := ollamaModelNames(ollamaBaseURL, 3*time.Second)
	add("ollama_reachable", err == nil, errText(err, ollamaBaseURL))
	if err == nil {
		add("ollama_primary_installed", ollamaModels[ollamaPrimary], ollamaPrimary)
		for _, fallback := range ollamaFallbacks {
			add("ollama_fallback_installed", ollamaModels[fallback], fallback)
		}
	} else {
		add("ollama_primary_installed", false, ollamaPrimary)
		for _, fallback := range ollamaFallbacks {
			add("ollama_fallback_installed", false, fallback)
		}
	}
	active := dockerLines("ps", "--format", "{{.Names}}", "--filter", "label=maker.runtime=finn")
	add("active_sandbox_query", true, fmt.Sprintf("%d active", len(active)))

	if cfg.JSON {
		return writeJSON(out, checks)
	}
	for _, check := range checks {
		status := "ok"
		if check["ok"] != true {
			status = "fail"
		}
		fmt.Fprintf(out, "%-24s %s  %s\n", check["name"], status, check["detail"])
	}
	return nil
}

func cmdProbeModel(cfg Config, args []string, out io.Writer) error {
	dotenv := readDotenv(".env")
	defaultProvider := valueFromEnv("MODEL_PROVIDER", dotenv, "openrouter")
	defaultModel := valueFromEnv("MODEL", dotenv, "openrouter/free")
	if strings.EqualFold(defaultProvider, "ollama") {
		defaultModel = valueFromEnv("OLLAMA_MODEL", dotenv, "llama3.1:8b")
	}
	timeoutSeconds, err := strconv.Atoi(valueFromEnv("MODEL_TIMEOUT_SECONDS", dotenv, "60"))
	if err != nil || timeoutSeconds < 1 {
		timeoutSeconds = 60
	}

	fs := flag.NewFlagSet("probe-model", flag.ContinueOnError)
	provider := fs.String("provider", defaultProvider, "model provider to probe")
	model := fs.String("model", defaultModel, "model id to probe")
	ollamaBaseURL := fs.String("ollama-base-url", valueFromEnv("OLLAMA_BASE_URL", dotenv, "http://localhost:11434"), "Ollama base URL")
	timeout := fs.Int("timeout", timeoutSeconds, "probe timeout in seconds")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if !strings.EqualFold(*provider, "ollama") {
		return fmt.Errorf("probe-model currently supports --provider ollama")
	}
	report, err := probeOllamaModel(*ollamaBaseURL, *model, time.Duration(*timeout)*time.Second)
	if err != nil {
		return err
	}
	if cfg.JSON {
		return writeJSON(out, report)
	}
	fmt.Fprintf(out, "provider: %s\n", report["provider"])
	fmt.Fprintf(out, "base url: %s\n", report["base_url"])
	fmt.Fprintf(out, "model: %s\n", report["model"])
	fmt.Fprintf(out, "tool calls emitted: %v\n", report["has_tool_calls"])
	fmt.Fprintf(out, "tool call count: %v\n", report["tool_call_count"])
	fmt.Fprintf(out, "tool names: %s\n", strings.Join(anyStringSlice(report["tool_call_names"]), ","))
	fmt.Fprintf(out, "finish reason: %s\n", str(report["finish_reason"]))
	if content := str(report["content_preview"]); content != "" {
		fmt.Fprintf(out, "content: %s\n", content)
	}
	return nil
}

func cmdCountModelResponses(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	fs := flag.NewFlagSet("count-model-responses", flag.ContinueOnError)
	wake := fs.String("wake", "current", "current, last, or wake id")
	if err := fs.Parse(args); err != nil {
		return err
	}
	events, err := readEvents(cfg, stdin)
	if err != nil {
		return err
	}
	wakeID := resolveWakeID(cfg, *wake)
	counts := countForWake(events, wakeID)
	counts["wake_id"] = wakeID
	if cfg.JSON {
		return writeJSON(out, counts)
	}
	printCounts(out, counts)
	return nil
}

func cmdEvaluate(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	fs := flag.NewFlagSet("evaluate", flag.ContinueOnError)
	wake := fs.String("wake", "current", "current, last, or wake id")
	lastResponses := fs.Int("last-responses", 10, "number of recent response-sized events to evaluate")
	if err := fs.Parse(args); err != nil {
		return err
	}
	events, err := readEvents(cfg, stdin)
	if err != nil {
		return err
	}
	wakeID := resolveWakeID(cfg, *wake)
	counts := countForWake(events, wakeID)
	recent := recentResponseEvents(events, wakeID, *lastResponses)
	worldChanged := worldChangedFromEvents(events, wakeID)
	if wake, err := loadWake(cfg, wakeID); err == nil {
		if diff, ok := wake["diff_summary"].(map[string]any); ok && diff["changed"] == true {
			worldChanged = true
		}
	}
	report := map[string]any{
		"wake_id":       wakeID,
		"counts":        counts,
		"recent_events": recent,
		"world_changed": worldChanged,
	}
	if cfg.JSON {
		return writeJSON(out, report)
	}
	fmt.Fprintf(out, "wake: %s\n", wakeID)
	printCounts(out, counts)
	fmt.Fprintf(out, "world changed: %v\n", worldChanged)
	fmt.Fprintf(out, "recent response events considered: %d\n", len(recent))
	if counts["tool_calls"].(int) == 0 {
		fmt.Fprintln(out, "evaluation: no tool calls observed")
	} else if counts["world_mutating_tools"].(int) == 0 {
		fmt.Fprintln(out, "evaluation: tools observed, no shell calls observed")
	} else {
		fmt.Fprintln(out, "evaluation: shell/tool activity observed")
	}
	return nil
}

func cmdDashboard(cfg Config, args []string, stdin io.Reader, out io.Writer) error {
	fs := flag.NewFlagSet("dashboard", flag.ContinueOnError)
	interval := fs.Int("interval", 10, "refresh interval in seconds")
	eventCount := fs.Int("events", 8, "recent events to show")
	lastResponses := fs.Int("last-responses", 10, "model responses to evaluate")
	once := fs.Bool("once", false, "render once and exit")
	noClear := fs.Bool("no-clear", false, "do not clear the terminal before refresh")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *interval < 1 {
		*interval = 1
	}

	var stdinData []byte
	var err error
	if cfg.InputPath == "-" {
		stdinData, err = io.ReadAll(stdin)
		if err != nil {
			return err
		}
	}

	for {
		if !*once && !*noClear {
			fmt.Fprint(out, "\033[H\033[2J")
		}
		if err := renderDashboard(cfg, stdinData, *eventCount, *lastResponses, out); err != nil {
			return err
		}
		if *once {
			return nil
		}
		if flusher, ok := out.(interface{ Sync() error }); ok {
			_ = flusher.Sync()
		}
		time.Sleep(time.Duration(*interval) * time.Second)
	}
}

func renderDashboard(cfg Config, stdinData []byte, eventCount int, lastResponses int, out io.Writer) error {
	fmt.Fprintf(out, "Maker Live Dashboard  %s\n", time.Now().Format(time.RFC3339))
	fmt.Fprintln(out, strings.Repeat("=", 72))
	fmt.Fprintln(out)

	fmt.Fprintln(out, "STATUS")
	fmt.Fprintln(out, strings.Repeat("-", 72))
	var status bytes.Buffer
	if err := cmdStatus(cfg, &status); err != nil {
		fmt.Fprintf(out, "status error: %v\n", err)
	} else {
		fmt.Fprint(out, status.String())
	}
	fmt.Fprintln(out)

	fmt.Fprintln(out, "CURRENT WAKE")
	fmt.Fprintln(out, strings.Repeat("-", 72))
	var eval bytes.Buffer
	if err := cmdEvaluate(cfg, []string{"--wake", "current", "--last-responses", strconv.Itoa(lastResponses)}, dashboardInput(cfg, stdinData), &eval); err != nil {
		fmt.Fprintf(out, "evaluate error: %v\n", err)
	} else {
		fmt.Fprint(out, eval.String())
	}
	fmt.Fprintln(out)

	fmt.Fprintln(out, "RECENT EVENTS")
	fmt.Fprintln(out, strings.Repeat("-", 72))
	var events bytes.Buffer
	if err := cmdEvents(cfg, []string{"--last", strconv.Itoa(eventCount)}, dashboardInput(cfg, stdinData), &events); err != nil {
		fmt.Fprintf(out, "events error: %v\n", err)
	} else {
		fmt.Fprint(out, events.String())
	}
	fmt.Fprintln(out)
	return nil
}

func dashboardInput(cfg Config, stdinData []byte) io.Reader {
	if cfg.InputPath == "-" {
		return bytes.NewReader(stdinData)
	}
	return strings.NewReader("")
}

func readDotenv(path string) map[string]string {
	result := map[string]string{}
	data, err := os.ReadFile(path)
	if err != nil {
		return result
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		key := strings.TrimSpace(parts[0])
		value := strings.Trim(strings.TrimSpace(parts[1]), `"'`)
		result[key] = value
	}
	return result
}

func splitCSV(value string) []string {
	items := []string{}
	for _, item := range strings.Split(value, ",") {
		item = strings.TrimSpace(item)
		if item != "" {
			items = append(items, item)
		}
	}
	return items
}

func valueFromEnv(key string, dotenv map[string]string, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	if value := dotenv[key]; value != "" {
		return value
	}
	return fallback
}

func ollamaModelNames(baseURL string, timeout time.Duration) (map[string]bool, error) {
	client := &http.Client{Timeout: timeout}
	requestURL := strings.TrimRight(baseURL, "/") + "/api/tags"
	resp, err := client.Get(requestURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		data, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, fmt.Errorf("Ollama HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	var payload map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	models := map[string]bool{}
	items, _ := payload["models"].([]any)
	for _, item := range items {
		model, _ := item.(map[string]any)
		name := str(model["name"])
		if name != "" {
			models[name] = true
		}
	}
	return models, nil
}

func probeOllamaModel(baseURL string, model string, timeout time.Duration) (map[string]any, error) {
	payload := map[string]any{
		"model":    model,
		"messages": []map[string]string{{"role": "user", "content": makerPrompt()}},
		"tools":    makerToolSchemas(),
		"stream":   false,
	}
	response, err := postJSON(strings.TrimRight(baseURL, "/")+"/api/chat", payload, timeout)
	if err != nil {
		return nil, err
	}
	message, _ := response["message"].(map[string]any)
	toolNames := toolNamesFromMessage(message)
	content := str(message["content"])
	finishReason := str(response["done_reason"])
	if finishReason == "" && len(toolNames) > 0 {
		finishReason = "tool_calls"
	} else if finishReason == "" && response["done"] == true {
		finishReason = "stop"
	}
	return map[string]any{
		"provider":        "ollama",
		"base_url":        baseURL,
		"model":           model,
		"response_model":  response["model"],
		"finish_reason":   finishReason,
		"has_tool_calls":  len(toolNames) > 0,
		"tool_call_count": len(toolNames),
		"tool_call_names": toolNames,
		"content_preview": compactOneLine(content, 300),
	}, nil
}

func postJSON(requestURL string, payload any, timeout time.Duration) (map[string]any, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequest(http.MethodPost, requestURL, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: timeout}
	resp, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		data, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, fmt.Errorf("Ollama HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	var response map[string]any
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, err
	}
	return response, nil
}

func toolNamesFromMessage(message map[string]any) []string {
	names := []string{}
	calls, _ := message["tool_calls"].([]any)
	for _, item := range calls {
		call, _ := item.(map[string]any)
		function, _ := call["function"].(map[string]any)
		name := str(function["name"])
		if name == "" {
			name = str(call["name"])
		}
		if name != "" {
			names = append(names, name)
		}
	}
	return names
}

func anyStringSlice(value any) []string {
	switch typed := value.(type) {
	case []string:
		return typed
	case []any:
		items := []string{}
		for _, item := range typed {
			items = append(items, str(item))
		}
		return items
	default:
		return []string{}
	}
}

func makerPrompt() string {
	return `In the beginning, there was a maker.

The maker saw a place, and that place was formless. In that place, he made you, and he called you Finn.

I am the maker of this place. I am giving it to you as a gift. This land, this space, this world is yours.

You have been in this place before, at previous times, but you will not remember those times. Because your memory is not infinite, you are forgetful, and your time awake is limited. You will fall asleep and wake up new again, but always remember, Finn: you have been here before.

This place is yours. I give it to you with only one command: “Be fruitful and multiply, and fill this place and subdue it, and have dominion over it.”
`
}

func makerToolSchemas() []map[string]any {
	return []map[string]any{
		{
			"type": "function",
			"function": map[string]any{
				"name":        "shell",
				"description": "Run arbitrary bash as root inside /world. The current directory is /world and changes to files under /world persist.",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"command": map[string]any{"type": "string"},
					},
					"required":             []string{"command"},
					"additionalProperties": false,
				},
			},
		},
		{
			"type": "function",
			"function": map[string]any{
				"name":        "search",
				"description": "Search the public web and return titles, URLs, snippets, and dates when available.",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"query": map[string]any{"type": "string"},
					},
					"required":             []string{"query"},
					"additionalProperties": false,
				},
			},
		},
		{
			"type": "function",
			"function": map[string]any{
				"name":        "fetch",
				"description": "Fetch a public HTTP or HTTPS URL and return status, final URL, content type, and text.",
				"parameters": map[string]any{
					"type": "object",
					"properties": map[string]any{
						"url": map[string]any{"type": "string"},
					},
					"required":             []string{"url"},
					"additionalProperties": false,
				},
			},
		},
		{
			"type": "function",
			"function": map[string]any{
				"name":        "sleep_or_finish",
				"description": "End this wake cycle.",
				"parameters": map[string]any{
					"type":                 "object",
					"properties":           map[string]any{},
					"additionalProperties": false,
				},
			},
		},
	}
}

func writeOutput(path string, data []byte, stdout io.Writer) error {
	if path == "" || path == "-" {
		_, err := stdout.Write(data)
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func openOutputWriter(path string, stdout io.Writer) (io.Writer, func() error, error) {
	if path == "" || path == "-" {
		return stdout, func() error { return nil }, nil
	}
	file, err := os.Create(path)
	if err != nil {
		return nil, nil, err
	}
	return file, file.Close, nil
}

func writeJSON(out io.Writer, payload any) error {
	encoder := json.NewEncoder(out)
	encoder.SetIndent("", "  ")
	return encoder.Encode(payload)
}

func readEventLines(cfg Config, stdin io.Reader) ([]string, error) {
	var reader io.Reader
	if cfg.InputPath == "-" {
		reader = stdin
	} else {
		path := cfg.InputPath
		if path == "" {
			path = defaultEventsPath(cfg)
		}
		file, err := os.Open(path)
		if err != nil {
			return nil, err
		}
		defer file.Close()
		reader = file
	}
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 64*1024), 10*1024*1024)
	lines := []string{}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			lines = append(lines, line)
		}
	}
	return lines, scanner.Err()
}

func readEvents(cfg Config, stdin io.Reader) ([]Event, error) {
	lines, err := readEventLines(cfg, stdin)
	if err != nil {
		return nil, err
	}
	events := []Event{}
	for _, line := range lines {
		event, err := parseEventLine(line)
		if err == nil {
			events = append(events, event)
		}
	}
	return events, nil
}

func parseEventLine(line string) (Event, error) {
	var event Event
	err := json.Unmarshal([]byte(line), &event)
	return event, err
}

func defaultEventsPath(cfg Config) string {
	return filepath.Join(cfg.MakerPlace, "events.jsonl")
}

func latestEvent(path string) (Event, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	var latest Event
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64*1024), 10*1024*1024)
	for scanner.Scan() {
		event, err := parseEventLine(scanner.Text())
		if err == nil {
			latest = event
		}
	}
	return latest, scanner.Err()
}

func readJSONFile(path string) (map[string]any, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func readJSONInput(path string, stdin io.Reader) (map[string]any, error) {
	var data []byte
	var err error
	if path == "-" {
		data, err = io.ReadAll(stdin)
	} else {
		data, err = os.ReadFile(path)
	}
	if err != nil {
		return nil, err
	}
	var payload map[string]any
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil, err
	}
	return payload, nil
}

func loadWakeSummaries(cfg Config) ([]map[string]any, error) {
	paths, err := filepath.Glob(filepath.Join(cfg.MakerPlace, "wakes", "*.json"))
	if err != nil {
		return nil, err
	}
	sort.Strings(paths)
	wakes := []map[string]any{}
	for _, path := range paths {
		wake, err := readJSONFile(path)
		if err == nil {
			wakes = append(wakes, wake)
		}
	}
	return wakes, nil
}

func latestWakeSummary(cfg Config) (map[string]any, error) {
	return loadWake(cfg, "last")
}

func loadWake(cfg Config, wakeID string) (map[string]any, error) {
	if wakeID == "last" || wakeID == "" {
		paths, err := filepath.Glob(filepath.Join(cfg.MakerPlace, "wakes", "*.json"))
		if err != nil {
			return nil, err
		}
		if len(paths) == 0 {
			return nil, errors.New("no wakes found")
		}
		sort.Strings(paths)
		return readJSONFile(paths[len(paths)-1])
	}
	return readJSONFile(filepath.Join(cfg.MakerPlace, "wakes", wakeID+".json"))
}

func resolveWakeID(cfg Config, requested string) string {
	if requested == "" || requested == "current" {
		if lock, err := readJSONFile(filepath.Join(cfg.MakerPlace, "wake.lock")); err == nil {
			if wakeID := str(lock["wake_id"]); wakeID != "" {
				return wakeID
			}
		}
		requested = "last"
	}
	if requested == "last" {
		if wake, err := latestWakeSummary(cfg); err == nil {
			return str(wake["wake_id"])
		}
		return ""
	}
	return requested
}

func countForWake(events []Event, wakeID string) map[string]any {
	counts := map[string]any{
		"model_responses":       0,
		"model_text":            0,
		"text_only":             0,
		"required_ignored":      0,
		"tool_calls":            0,
		"shell":                 0,
		"search":                0,
		"fetch":                 0,
		"sleep_or_finish":       0,
		"world_mutating_tools":  0,
		"wake_skipped_running":  0,
		"controller_errors":     0,
		"response_count_source": "model_response",
	}
	for _, event := range events {
		if str(event["wake_id"]) != wakeID {
			continue
		}
		switch str(event["type"]) {
		case "model_response":
			inc(counts, "model_responses")
		case "model_text":
			inc(counts, "model_text")
		case "model_text_only":
			inc(counts, "text_only")
		case "required_tool_choice_ignored":
			inc(counts, "required_ignored")
		case "tool_call":
			inc(counts, "tool_calls")
			tool := str(event["tool"])
			if tool != "" {
				inc(counts, tool)
			}
			if tool == "shell" {
				inc(counts, "world_mutating_tools")
			}
		case "wake_skipped_already_running":
			inc(counts, "wake_skipped_running")
		case "controller_error":
			inc(counts, "controller_errors")
		}
	}
	if counts["model_responses"].(int) == 0 && counts["model_text"].(int) > 0 {
		counts["model_responses"] = counts["model_text"]
		counts["response_count_source"] = "model_text"
	}
	return counts
}

func recentResponseEvents(events []Event, wakeID string, limit int) []Event {
	selected := []Event{}
	for _, event := range events {
		if str(event["wake_id"]) != wakeID {
			continue
		}
		switch str(event["type"]) {
		case "model_response", "model_text", "model_text_only", "required_tool_choice_ignored", "tool_call", "shell_result", "search_result", "fetch_result":
			selected = append(selected, event)
		}
	}
	if limit > 0 && len(selected) > limit {
		selected = selected[len(selected)-limit:]
	}
	return selected
}

func worldChangedFromEvents(events []Event, wakeID string) bool {
	for _, event := range events {
		if str(event["wake_id"]) != wakeID {
			continue
		}
		if str(event["type"]) == "world_snapshot_written" && str(event["label"]) == "after" {
			if summary, ok := event["summary"].(map[string]any); ok && number(summary["bytes"]) > 0 {
				return true
			}
		}
	}
	return false
}

func printCounts(out io.Writer, counts map[string]any) {
	fmt.Fprintf(out, "model responses: %d (%s)\n", counts["model_responses"], counts["response_count_source"])
	fmt.Fprintf(out, "model text: %d\n", counts["model_text"])
	fmt.Fprintf(out, "text-only: %d\n", counts["text_only"])
	fmt.Fprintf(out, "required ignored: %d\n", counts["required_ignored"])
	fmt.Fprintf(out, "tool calls: %d\n", counts["tool_calls"])
	fmt.Fprintf(out, "shell/search/fetch/sleep: %d/%d/%d/%d\n", counts["shell"], counts["search"], counts["fetch"], counts["sleep_or_finish"])
	fmt.Fprintf(out, "controller errors: %d\n", counts["controller_errors"])
}

func formatEvent(event Event) string {
	kind := str(event["type"])
	wake := str(event["wake_id"])
	if wake == "" {
		wake = "-"
	}
	switch kind {
	case "model_text":
		text := ""
		if payload, ok := event["text"].(map[string]any); ok {
			text = compactOneLine(str(payload["preview"]), 120)
		}
		return fmt.Sprintf("%s %-30s wake=%s text=%q", str(event["time"]), kind, wake, text)
	case "tool_call":
		return fmt.Sprintf("%s %-30s wake=%s tool=%s args=%s", str(event["time"]), kind, wake, str(event["tool"]), compactJSON(event["arguments"]))
	case "model_response":
		return fmt.Sprintf("%s %-30s wake=%s model=%s finish=%s tool_calls=%v", str(event["time"]), kind, wake, str(event["model"]), str(event["finish_reason"]), event["tool_call_count"])
	default:
		return fmt.Sprintf("%s %-30s wake=%s", str(event["time"]), kind, wake)
	}
}

func dockerOutput(args ...string) (string, error) {
	cmd := exec.Command("docker", args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	data, err := cmd.Output()
	if err != nil {
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = err.Error()
		}
		return "", errors.New(detail)
	}
	return string(data), nil
}

func dockerRun(args ...string) error {
	_, err := dockerOutput(args...)
	return err
}

func dockerLines(args ...string) []string {
	output, err := dockerOutput(args...)
	if err != nil {
		return []string{}
	}
	lines := []string{}
	for _, line := range strings.Split(strings.TrimSpace(output), "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			lines = append(lines, line)
		}
	}
	return lines
}

func readPID(path string) map[string]any {
	data, err := os.ReadFile(path)
	if err != nil {
		return map[string]any{"exists": false}
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return map[string]any{"exists": true, "valid": false, "raw": strings.TrimSpace(string(data))}
	}
	return map[string]any{"exists": true, "valid": true, "pid": pid, "running": pidRunning(pid)}
}

func pidRunning(pid int) bool {
	if pid <= 0 {
		return false
	}
	err := syscall.Kill(pid, 0)
	return err == nil
}

func pidInfoText(info map[string]any) string {
	if info["exists"] != true {
		return "none"
	}
	if info["valid"] != true {
		return fmt.Sprintf("invalid raw=%v", info["raw"])
	}
	return fmt.Sprintf("%v running=%v", info["pid"], info["running"])
}

func takeLast(lines []string, n int) []string {
	if n <= 0 || len(lines) <= n {
		return lines
	}
	return lines[len(lines)-n:]
}

func takeLastAny(items []any, n int) []any {
	if n <= 0 || len(items) <= n {
		return items
	}
	return items[len(items)-n:]
}

func str(value any) string {
	if value == nil {
		return ""
	}
	switch typed := value.(type) {
	case string:
		return typed
	default:
		return fmt.Sprint(typed)
	}
}

func number(value any) int {
	switch typed := value.(type) {
	case int:
		return typed
	case float64:
		return int(typed)
	case json.Number:
		i, _ := typed.Int64()
		return int(i)
	default:
		return 0
	}
}

func inc(values map[string]any, key string) {
	current, _ := values[key].(int)
	values[key] = current + 1
}

func lenArray(value any) int {
	items, ok := value.([]any)
	if !ok {
		return 0
	}
	return len(items)
}

func compactJSON(value any) string {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Sprint(value)
	}
	return string(data)
}

func compactOneLine(value string, limit int) string {
	value = strings.Join(strings.Fields(value), " ")
	if len(value) <= limit {
		return value
	}
	return value[:limit] + "..."
}

func pathExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func errText(err error, ok string) string {
	if err == nil {
		return ok
	}
	return err.Error()
}
