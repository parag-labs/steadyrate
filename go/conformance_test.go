package steadyrate

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type vectors struct {
	TimelineMs []int64 `json:"timeline_ms"`
	Cases      []struct {
		Strategy  string         `json:"strategy"`
		Params    map[string]int `json:"params"`
		Decisions []int          `json:"decisions"`
	} `json:"cases"`
}

func build(strategy string, p map[string]int) Limiter {
	switch strategy {
	case "token_bucket":
		return NewTokenBucket(p["capacity"], p["refill_per_sec"])
	case "leaky_bucket":
		return NewLeakyBucket(p["capacity"], p["leak_per_sec"])
	case "fixed_window":
		return NewFixedWindow(p["limit"], p["window_ms"])
	case "sliding_window_log":
		return NewSlidingWindowLog(p["limit"], p["window_ms"])
	case "sliding_window_counter":
		return NewSlidingWindowCounter(p["limit"], p["window_ms"])
	}
	panic("unknown strategy " + strategy)
}

func TestConformance(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "conformance", "vectors.json"))
	if err != nil {
		t.Fatalf("read vectors: %v", err)
	}
	var v vectors
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("parse: %v", err)
	}
	for _, c := range v.Cases {
		lim := build(c.Strategy, c.Params)
		for i, ts := range v.TimelineMs {
			want := c.Decisions[i] == 1
			if got := lim.Allow(ts); got != want {
				t.Errorf("%s at t=%d (idx %d): got %v want %v", c.Strategy, ts, i, got, want)
			}
		}
	}
}
