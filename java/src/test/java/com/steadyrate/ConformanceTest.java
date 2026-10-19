package com.steadyrate;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.steadyrate.Limiters.FixedWindow;
import com.steadyrate.Limiters.LeakyBucket;
import com.steadyrate.Limiters.Limiter;
import com.steadyrate.Limiters.SlidingWindowCounter;
import com.steadyrate.Limiters.SlidingWindowLog;
import com.steadyrate.Limiters.TokenBucket;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import org.json.JSONObject;
import org.junit.jupiter.api.Test;

class ConformanceTest {

    private static JSONObject vectors() throws IOException {
        Path dir = Paths.get("").toAbsolutePath();
        while (dir != null && !Files.exists(dir.resolve("conformance/vectors.json"))) {
            dir = dir.getParent();
        }
        if (dir == null) throw new IOException("conformance/vectors.json not found");
        return new JSONObject(Files.readString(dir.resolve("conformance/vectors.json")));
    }

    private static Limiter build(String strategy, JSONObject p) {
        switch (strategy) {
            case "token_bucket":
                return new TokenBucket(p.getInt("capacity"), p.getInt("refill_per_sec"));
            case "leaky_bucket":
                return new LeakyBucket(p.getInt("capacity"), p.getInt("leak_per_sec"));
            case "fixed_window":
                return new FixedWindow(p.getInt("limit"), p.getInt("window_ms"));
            case "sliding_window_log":
                return new SlidingWindowLog(p.getInt("limit"), p.getInt("window_ms"));
            case "sliding_window_counter":
                return new SlidingWindowCounter(p.getInt("limit"), p.getInt("window_ms"));
            default:
                throw new IllegalArgumentException(strategy);
        }
    }

    @Test
    void allStrategiesMatchVectors() throws IOException {
        JSONObject v = vectors();
        var timeline = v.getJSONArray("timeline_ms");
        var cases = v.getJSONArray("cases");
        for (int c = 0; c < cases.length(); c++) {
            JSONObject case_ = cases.getJSONObject(c);
            Limiter lim = build(case_.getString("strategy"), case_.getJSONObject("params"));
            var decisions = case_.getJSONArray("decisions");
            for (int i = 0; i < timeline.length(); i++) {
                boolean want = decisions.getInt(i) == 1;
                assertEquals(want, lim.allow(timeline.getLong(i)),
                        case_.getString("strategy") + " idx " + i);
            }
        }
    }
}
