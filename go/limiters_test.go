package steadyrate

import "testing"

func TestTokenBucketBurstThenThrottle(t *testing.T) {
	tb := NewTokenBucket(5, 1)
	allowed := 0
	for i := 0; i < 5; i++ {
		if tb.Allow(0) {
			allowed++
		}
	}
	if allowed != 5 {
		t.Fatalf("want 5 allowed in burst, got %d", allowed)
	}
	if tb.Allow(0) {
		t.Fatal("6th request at t=0 should be rejected")
	}
	if !tb.Allow(2000) {
		t.Fatal("after 2s a token should have refilled")
	}
}

func TestFixedWindowEdgeBurst(t *testing.T) {
	fw := NewFixedWindow(2, 1000)
	if !fw.Allow(999) || !fw.Allow(999) {
		t.Fatal("two at end of window 0 should be allowed")
	}
	if !fw.Allow(1000) || !fw.Allow(1000) {
		t.Fatal("two at start of window 1 should be allowed (the 2x edge burst)")
	}
}

func TestSlidingWindowLogPreventsEdgeBurst(t *testing.T) {
	sw := NewSlidingWindowLog(2, 1000)
	if !sw.Allow(999) || !sw.Allow(999) {
		t.Fatal("first two should be allowed")
	}
	if sw.Allow(1000) {
		t.Fatal("sliding log must reject the boundary burst")
	}
}

func TestLeakyBucketLeaks(t *testing.T) {
	lb := NewLeakyBucket(3, 1)
	for i := 0; i < 3; i++ {
		if !lb.Allow(0) {
			t.Fatal("queue should accept up to capacity")
		}
	}
	if lb.Allow(0) {
		t.Fatal("full queue should reject")
	}
	if !lb.Allow(1000) {
		t.Fatal("after 1s one slot should have leaked")
	}
}
