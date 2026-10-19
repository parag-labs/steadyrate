use serde_json::Value;
use std::fs;
use std::path::Path;
use steadyrate::{
    FixedWindow, LeakyBucket, Limiter, SlidingWindowCounter, SlidingWindowLog, TokenBucket,
};

fn build(strategy: &str, p: &Value) -> Box<dyn Limiter> {
    let i = |k: &str| p[k].as_i64().unwrap();
    match strategy {
        "token_bucket" => Box::new(TokenBucket::new(i("capacity"), i("refill_per_sec"))),
        "leaky_bucket" => Box::new(LeakyBucket::new(i("capacity"), i("leak_per_sec"))),
        "fixed_window" => Box::new(FixedWindow::new(i("limit"), i("window_ms"))),
        "sliding_window_log" => {
            Box::new(SlidingWindowLog::new(i("limit") as usize, i("window_ms")))
        }
        "sliding_window_counter" => Box::new(SlidingWindowCounter::new(i("limit"), i("window_ms"))),
        _ => panic!("unknown strategy {strategy}"),
    }
}

#[test]
fn conformance() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("conformance")
        .join("vectors.json");
    let v: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
    let timeline: Vec<i64> = v["timeline_ms"]
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_i64().unwrap())
        .collect();
    for case in v["cases"].as_array().unwrap() {
        let strategy = case["strategy"].as_str().unwrap();
        let mut lim = build(strategy, &case["params"]);
        let decisions = case["decisions"].as_array().unwrap();
        for (idx, &ts) in timeline.iter().enumerate() {
            let want = decisions[idx].as_i64().unwrap() == 1;
            assert_eq!(lim.allow(ts), want, "{strategy} at idx {idx}");
        }
    }
}
