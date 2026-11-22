using System.Text.Json;
using Factory.Config;

namespace Factory.Drivers;

/// <summary>
/// Codex driver: <c>codex exec</c> with JSONL events. Flags, checked against <c>codex exec --help</c>:
/// <list type="bullet">
/// <item><c>--sandbox read-only</c>: commands the model runs may read files, not write them.</item>
/// <item><c>--ephemeral</c>: the run leaves no session files.</item>
/// <item><c>--disable hooks</c>: the factory's own hooks can't trigger themselves.</item>
/// <item><c>--skip-git-repo-check</c>: runs also work in a copy of the project without .git.</item>
/// <item><c>--output-last-message FILE</c>: the final answer, read from a file instead of from events.</item>
/// <item><c>-</c>: the prompt comes from stdin.</item>
/// </list>
/// The answer comes from the file, a documented flag. Events only add the session id and token
/// counts, and lines we don't recognize are skipped, so a format change loses numbers, never the answer.
/// </summary>
public sealed class CodexDriver : IDriver
{
    public const string LastMessageFile = "last-message.txt";

    public string Name => "codex";

    public string Executable => "codex";

    public IReadOnlyList<string> Arguments(ModelChoice choice, string scratchDirectory)
    {
        var args = new List<string>
        {
            "exec", "--json", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
            "--disable", "hooks", "--output-last-message", Path.Combine(scratchDirectory, LastMessageFile),
        };
        if (choice.Model.Length > 0)
        {
            args.AddRange(["--model", choice.Model]);
        }
        if (choice.Effort.Length > 0)
        {
            args.AddRange(["-c", $"model_reasoning_effort=\"{choice.Effort}\""]);
        }
        args.Add("-");
        return args;
    }

    public Reply Parse(string stdout, string scratchDirectory)
    {
        var sessionId = "";
        CodexUsage? usage = null;
        var errors = new List<string>();
        foreach (var line in stdout.Split('\n', StringSplitOptions.RemoveEmptyEntries))
        {
            var ev = TryRead(line);
            switch (ev?.Type)
            {
                case "thread.started" when !string.IsNullOrEmpty(ev.ThreadId):
                    sessionId = ev.ThreadId;
                    break;
                case "turn.completed" when ev.Usage is not null:
                    usage = ev.Usage;
                    break;
                case "error" or "turn.failed":
                    errors.Add(ev.Message ?? ev.Error?.Message ?? "");
                    break;
            }
        }

        var lastMessage = Path.Combine(scratchDirectory, LastMessageFile);
        var text = File.Exists(lastMessage) ? File.ReadAllText(lastMessage).Trim() : "";
        if (text.Length == 0)
        {
            var reason = errors.LastOrDefault(e => e.Length > 0) ?? "no error was reported";
            throw new HarnessException($"codex finished without a final message: {reason}");
        }

        return new Reply(
            Text: text,
            SessionId: sessionId,
            InputTokens: usage?.InputTokens,
            CachedInputTokens: usage?.CachedInputTokens,
            OutputTokens: usage?.OutputTokens);
    }

    private static CodexEvent? TryRead(string line)
    {
        try
        {
            return JsonSerializer.Deserialize<CodexEvent>(line, Json);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    /// <summary>One JSONL line from <c>codex exec --json</c>, reduced to the fields we use.</summary>
    private sealed record CodexEvent(
        string? Type = null,
        string? ThreadId = null,
        CodexUsage? Usage = null,
        string? Message = null,
        CodexError? Error = null);

    private sealed record CodexUsage(long InputTokens = 0, long CachedInputTokens = 0, long OutputTokens = 0);

    private sealed record CodexError(string? Message = null);
}
