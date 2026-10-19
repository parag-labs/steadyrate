using System.Text.Json;
using Xunit;

namespace SteadyRate.Tests;

public class ConformanceTests
{
    private static readonly JsonElement Vectors = Load();

    private static JsonElement Load()
    {
        var dir = AppContext.BaseDirectory;
        while (dir is not null && !File.Exists(Path.Combine(dir, "conformance", "vectors.json")))
        {
            dir = Directory.GetParent(dir)?.FullName;
        }
        if (dir is null) throw new FileNotFoundException("conformance/vectors.json");
        return JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "conformance", "vectors.json")))
            .RootElement.Clone();
    }

    private static ILimiter Build(string strategy, JsonElement p)
    {
        int I(string k) => p.GetProperty(k).GetInt32();
        return strategy switch
        {
            "token_bucket" => new TokenBucket(I("capacity"), I("refill_per_sec")),
            "leaky_bucket" => new LeakyBucket(I("capacity"), I("leak_per_sec")),
            "fixed_window" => new FixedWindow(I("limit"), I("window_ms")),
            "sliding_window_log" => new SlidingWindowLog(I("limit"), I("window_ms")),
            "sliding_window_counter" => new SlidingWindowCounter(I("limit"), I("window_ms")),
            _ => throw new ArgumentException(strategy),
        };
    }

    [Fact]
    public void AllStrategiesMatchVectors()
    {
        var timeline = Vectors.GetProperty("timeline_ms").EnumerateArray()
            .Select(x => x.GetInt64()).ToArray();
        foreach (var c in Vectors.GetProperty("cases").EnumerateArray())
        {
            var lim = Build(c.GetProperty("strategy").GetString()!, c.GetProperty("params"));
            var decisions = c.GetProperty("decisions").EnumerateArray().Select(x => x.GetInt32()).ToArray();
            for (var i = 0; i < timeline.Length; i++)
            {
                Assert.Equal(decisions[i] == 1, lim.Allow(timeline[i]));
            }
        }
    }
}
