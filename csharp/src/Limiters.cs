namespace SteadyRate;

/// <summary>
/// Five rate-limiting strategies behind one interface. Each takes the current time as
/// a parameter and decides with integer arithmetic only, so every language port agrees
/// byte-for-byte (see conformance/).
/// </summary>
public interface ILimiter
{
    bool Allow(long nowMs);
}

/// <summary>Fixed-point resolution for the bucket limiters: one whole token is Scale units.</summary>
public static class Constants
{
    public const long Scale = 1000;
}

public sealed class TokenBucket : ILimiter
{
    private readonly long _capacity;
    private readonly long _refillPerSec;
    private long _tokens;
    private long _lastMs;
    private bool _started;

    public TokenBucket(int capacity, int refillPerSec)
    {
        if (capacity < 1) throw new ArgumentOutOfRangeException(nameof(capacity));
        if (refillPerSec < 1) throw new ArgumentOutOfRangeException(nameof(refillPerSec));
        _capacity = capacity;
        _refillPerSec = refillPerSec;
        _tokens = capacity * Constants.Scale;
    }

    public bool Allow(long nowMs)
    {
        if (!_started) { _lastMs = nowMs; _started = true; }
        var elapsed = Math.Max(0, nowMs - _lastMs);
        _tokens = Math.Min(_capacity * Constants.Scale, _tokens + elapsed * _refillPerSec);
        _lastMs = nowMs;
        if (_tokens >= Constants.Scale) { _tokens -= Constants.Scale; return true; }
        return false;
    }
}

public sealed class LeakyBucket : ILimiter
{
    private readonly long _capacity;
    private readonly long _leakPerSec;
    private long _level;
    private long _lastMs;
    private bool _started;

    public LeakyBucket(int capacity, int leakPerSec)
    {
        if (capacity < 1) throw new ArgumentOutOfRangeException(nameof(capacity));
        if (leakPerSec < 1) throw new ArgumentOutOfRangeException(nameof(leakPerSec));
        _capacity = capacity;
        _leakPerSec = leakPerSec;
    }

    public bool Allow(long nowMs)
    {
        if (!_started) { _lastMs = nowMs; _started = true; }
        var elapsed = Math.Max(0, nowMs - _lastMs);
        _level = Math.Max(0, _level - elapsed * _leakPerSec);
        _lastMs = nowMs;
        if (_level + Constants.Scale <= _capacity * Constants.Scale) { _level += Constants.Scale; return true; }
        return false;
    }
}

public sealed class FixedWindow : ILimiter
{
    private readonly long _limit;
    private readonly long _windowMs;
    private long _window;
    private long _count;
    private bool _started;

    public FixedWindow(int limit, int windowMs)
    {
        if (limit < 1) throw new ArgumentOutOfRangeException(nameof(limit));
        if (windowMs < 1) throw new ArgumentOutOfRangeException(nameof(windowMs));
        _limit = limit;
        _windowMs = windowMs;
    }

    public bool Allow(long nowMs)
    {
        var window = Math.DivRem(nowMs, _windowMs, out _);
        if (!_started || window != _window) { _window = window; _count = 0; _started = true; }
        if (_count < _limit) { _count++; return true; }
        return false;
    }
}

public sealed class SlidingWindowLog : ILimiter
{
    private readonly int _limit;
    private readonly long _windowMs;
    private readonly Queue<long> _log = new();

    public SlidingWindowLog(int limit, int windowMs)
    {
        if (limit < 1) throw new ArgumentOutOfRangeException(nameof(limit));
        if (windowMs < 1) throw new ArgumentOutOfRangeException(nameof(windowMs));
        _limit = limit;
        _windowMs = windowMs;
    }

    public bool Allow(long nowMs)
    {
        var cutoff = nowMs - _windowMs;
        while (_log.Count > 0 && _log.Peek() <= cutoff) _log.Dequeue();
        if (_log.Count < _limit) { _log.Enqueue(nowMs); return true; }
        return false;
    }
}

public sealed class SlidingWindowCounter : ILimiter
{
    private readonly long _limit;
    private readonly long _windowMs;
    private long _window;
    private long _current;
    private long _previous;
    private bool _started;

    public SlidingWindowCounter(int limit, int windowMs)
    {
        if (limit < 1) throw new ArgumentOutOfRangeException(nameof(limit));
        if (windowMs < 1) throw new ArgumentOutOfRangeException(nameof(windowMs));
        _limit = limit;
        _windowMs = windowMs;
    }

    public bool Allow(long nowMs)
    {
        var window = Math.DivRem(nowMs, _windowMs, out _);
        if (!_started) { _window = window; _started = true; }
        else if (window == _window + 1) { _previous = _current; _current = 0; _window = window; }
        else if (window > _window) { _previous = 0; _current = 0; _window = window; }

        var intoWindow = nowMs - window * _windowMs;
        var lhs = _previous * (_windowMs - intoWindow) + _current * _windowMs + _windowMs;
        if (lhs <= _limit * _windowMs) { _current++; return true; }
        return false;
    }
}
