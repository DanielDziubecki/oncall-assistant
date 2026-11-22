using System.Text.Json;
using System.Text.Json.Serialization;
using Factory.Config;

namespace Factory.Drivers;

/// <summary>
/// Claude Code driver: <c>claude -p</c> with JSON output. Flags, checked against <c>claude --help</c>:
/// <list type="bullet">
/// <item><c>--tools ""</c>: no built-in tools, so a run answers from its prompt alone.</item>
/// <item><c>--safe-mode</c>: no CLAUDE.md, skills, hooks, plugins or MCP servers. The job's only
/// context is its prompt, and the factory's own hooks can't trigger themselves. The login still works.</item>
/// <item><c>--no-session-persistence</c>: the run leaves no session on disk.</item>
/// </list>
/// </summary>
public sealed class ClaudeDriver : IDriver
{
    public string Name => "claude";

    public string Executable => "claude";

    public IReadOnlyList<string> Arguments(ModelChoice choice, string scratchDirectory)
    {
        var args = new List<string>
        {
            "-p", "--output-format", "json", "--tools", "", "--safe-mode", "--no-session-persistence",
        };
        if (choice.Model.Length > 0)
        {
            args.AddRange(["--model", choice.Model]);
        }
        if (choice.Effort.Length > 0)
        {
            args.AddRange(["--effort", choice.Effort]);
        }
        return args;
    }

    public Reply Parse(string stdout, string scratchDirectory)
    {
        ClaudeResult? result;
        try
        {
            result = JsonSerializer.Deserialize<ClaudeResult>(stdout, Json);
        }
        catch (JsonException ex)
        {
            throw new HarnessException($"claude printed an unexpected result: {Shorten(stdout)}", ex);
        }
        if (result is null || result.Subtype is null)
        {
            throw new HarnessException($"claude printed an unexpected result: {Shorten(stdout)}");
        }
        if (result.IsError || result.Subtype != "success")
        {
            throw new HarnessException($"claude reported an error ({result.Subtype}): {Shorten(result.Result)}");
        }

        var usage = result.Usage;
        return new Reply(
            Text: result.Result,
            Model: result.ModelUsage?.Keys.FirstOrDefault() ?? "",
            SessionId: result.SessionId,
            CostUsd: result.TotalCostUsd,
            // Claude counts cache reads and writes apart from input_tokens; add them back.
            InputTokens: usage is null ? null : usage.InputTokens + usage.CacheReadInputTokens + usage.CacheCreationInputTokens,
            CachedInputTokens: usage?.CacheReadInputTokens,
            OutputTokens: usage?.OutputTokens);
    }

    private static string Shorten(string text) => text.Length <= 300 ? text : text[..300] + "…";

    private static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    /// <summary>The fields we read from <c>claude -p --output-format json</c>; the rest are ignored.</summary>
    private sealed record ClaudeResult(
        string? Subtype,
        bool IsError,
        string Result = "",
        string SessionId = "",
        double? TotalCostUsd = null,
        ClaudeUsage? Usage = null,
        [property: JsonPropertyName("modelUsage")] Dictionary<string, JsonElement>? ModelUsage = null);

    private sealed record ClaudeUsage(
        long InputTokens = 0,
        long CacheReadInputTokens = 0,
        long CacheCreationInputTokens = 0,
        long OutputTokens = 0);
}
