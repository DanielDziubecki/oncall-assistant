using Factory.Config;

namespace Factory.Drivers;

/// <summary>
/// Runs one harness headless: no conversation, read-only, context only from the prompt.
/// A driver is the only code that knows a vendor's command line, so adding a harness
/// means writing one driver.
/// </summary>
public interface IDriver
{
    /// <summary>The harness name used on the command line and in models.json, e.g. "claude".</summary>
    string Name { get; }

    /// <summary>The program to look up on PATH.</summary>
    string Executable { get; }

    /// <summary>The arguments for one run (without the program). The prompt goes on stdin, never here.</summary>
    IReadOnlyList<string> Arguments(ModelChoice choice, string scratchDirectory);

    /// <summary>Reads the reply from the run's stdout and any files it wrote to the scratch directory.</summary>
    Reply Parse(string stdout, string scratchDirectory);
}

/// <summary>
/// What a driver reads from one headless run.
/// Token counts mean the same for every harness: <see cref="InputTokens"/> counts all input,
/// including the part read from the cache, and <see cref="CachedInputTokens"/> counts that part.
/// <see cref="CostUsd"/> is what the harness reports; on a subscription it is an estimate.
/// </summary>
public sealed record Reply(
    string Text,
    string Model = "",
    string SessionId = "",
    double? CostUsd = null,
    long? InputTokens = null,
    long? CachedInputTokens = null,
    long? OutputTokens = null);

/// <summary>The harness gave no usable answer: missing, logged out, failed or too slow.</summary>
public sealed class HarnessException(string message, Exception? inner = null) : Exception(message, inner);
