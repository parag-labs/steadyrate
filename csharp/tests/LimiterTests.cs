using Xunit;

namespace SteadyRate.Tests;

public class LimiterTests
{
    [Fact]
    public void TokenBucketAllowsBurstThenThrottles()
    {
        var tb = new TokenBucket(5, 1);
        var allowed = 0;
        for (var i = 0; i < 5; i++) if (tb.Allow(0)) allowed++;
        Assert.Equal(5, allowed);
        Assert.False(tb.Allow(0));
        Assert.True(tb.Allow(2000));
    }

    [Fact]
    public void FixedWindowAllowsEdgeBurst()
    {
        var fw = new FixedWindow(2, 1000);
        Assert.True(fw.Allow(999));
        Assert.True(fw.Allow(999));
        Assert.True(fw.Allow(1000));
        Assert.True(fw.Allow(1000));
    }

    [Fact]
    public void SlidingWindowLogPreventsEdgeBurst()
    {
        var sw = new SlidingWindowLog(2, 1000);
        Assert.True(sw.Allow(999));
        Assert.True(sw.Allow(999));
        Assert.False(sw.Allow(1000));
    }
}
