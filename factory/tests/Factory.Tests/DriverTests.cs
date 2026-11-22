using Factory.Config;
using Factory.Drivers;

namespace Factory.Tests;

public sealed class ClaudeDriverTests
{
    private static readonly string Result = File.ReadAllText(Fakes.Fixture("claude-result.json"));
    private readonly ClaudeDriver driver = new();

    [Fact]
    public void Runs_headless_without_tools_or_project_config()
    {
        var args = driver.Arguments(new ModelChoice(), "/tmp/x");

        Assert.Equal("-p", args[0]);
        Assert.Equal("json", After(args, "--output-format"));
        Assert.Equal("", After(args, "--tools"));
        Assert.Contains("--safe-mode", args);
        Assert.Contains("--no-session-persistence", args);
        Assert.DoesNotContain("--model", args);
        Assert.DoesNotContain("--effort", args);
    }

    [Fact]
    public void Passes_model_and_effort_when_set()
    {
        var args = driver.Arguments(new ModelChoice("haiku", "low"), "/tmp/x");

        Assert.Equal("haiku", After(args, "--model"));
        Assert.Equal("low", After(args, "--effort"));
    }

    [Fact]
    public void Reads_text_model_cost_and_tokens()
    {
        var reply = driver.Parse(Result, "/tmp/x");

        Assert.Equal("OK", reply.Text);
        Assert.Equal("example-small-model", reply.Model);
        Assert.Equal("00000000-0000-4000-8000-000000000001", reply.SessionId);
        Assert.Equal(0.00062689, reply.CostUsd!.Value, 8);
        // Claude counts cache reads and writes apart from input_tokens; the reply adds them back.
        Assert.Equal(2 + 649 + 3091, reply.InputTokens);
        Assert.Equal(649, reply.CachedInputTokens);
        Assert.Equal(4, reply.OutputTokens);
    }

    [Fact]
    public void An_error_result_is_a_harness_error()
    {
        var failed = Result.Replace("\"is_error\": false", "\"is_error\": true")
            .Replace("\"result\": \"OK\"", "\"result\": \"Credit balance is too low\"");

        var ex = Assert.Throws<HarnessException>(() => driver.Parse(failed, "/tmp/x"));
        Assert.Contains("Credit balance is too low", ex.Message);
    }

    [Fact]
    public void Output_that_is_not_a_result_is_a_harness_error()
    {
        var ex = Assert.Throws<HarnessException>(() => driver.Parse("Welcome to Claude Code!", "/tmp/x"));
        Assert.Contains("unexpected result", ex.Message);
    }

    internal static string After(IReadOnlyList<string> args, string flag) => args[args.ToList().IndexOf(flag) + 1];
}

public sealed class CodexDriverTests : IDisposable
{
    private static readonly string Events = File.ReadAllText(Fakes.Fixture("codex-exec.synthetic.jsonl"));
    private readonly CodexDriver driver = new();
    private readonly string scratch = Directory.CreateTempSubdirectory("codex-test-").FullName;

    public void Dispose() => Directory.Delete(scratch, recursive: true);

    [Fact]
    public void Runs_read_only_ephemeral_and_reads_the_prompt_from_stdin()
    {
        var args = driver.Arguments(new ModelChoice(), scratch);

        Assert.Equal(["exec", "--json"], args.Take(2));
        Assert.Equal("read-only", ClaudeDriverTests.After(args, "--sandbox"));
        Assert.Contains("--ephemeral", args);
        Assert.Contains("--skip-git-repo-check", args);
        Assert.Equal("hooks", ClaudeDriverTests.After(args, "--disable"));
        Assert.Equal(Path.Combine(scratch, CodexDriver.LastMessageFile), ClaudeDriverTests.After(args, "--output-last-message"));
        Assert.Equal("-", args[^1]);
        Assert.DoesNotContain("--model", args);
        Assert.DoesNotContain("-c", args);
    }

    [Fact]
    public void Passes_model_and_reasoning_effort_when_set()
    {
        var args = driver.Arguments(new ModelChoice("small-codex", "low"), scratch);

        Assert.Equal("small-codex", ClaudeDriverTests.After(args, "--model"));
        Assert.Equal("model_reasoning_effort=\"low\"", ClaudeDriverTests.After(args, "-c"));
        Assert.Equal("-", args[^1]);
    }

    [Fact]
    public void Reads_text_from_the_last_message_and_numbers_from_events()
    {
        File.WriteAllText(Path.Combine(scratch, CodexDriver.LastMessageFile), "OK\n");

        var reply = driver.Parse(Events, scratch);

        Assert.Equal("OK", reply.Text);
        Assert.Equal("00000000-0000-4000-8000-0000000000c1", reply.SessionId);
        Assert.Equal(2400, reply.InputTokens);
        Assert.Equal(1800, reply.CachedInputTokens);
        Assert.Equal(5, reply.OutputTokens);
        Assert.Null(reply.CostUsd);
    }

    [Fact]
    public void Skips_lines_it_does_not_recognize()
    {
        File.WriteAllText(Path.Combine(scratch, CodexDriver.LastMessageFile), "OK");

        var reply = driver.Parse("not json\n{\"type\":\"something.new\",\"payload\":[1,2]}\n" + Events, scratch);

        Assert.Equal("OK", reply.Text);
        Assert.Equal(5, reply.OutputTokens);
    }

    [Fact]
    public void Without_a_final_message_reports_the_last_error()
    {
        var events = "{\"type\":\"turn.failed\",\"error\":{\"message\":\"usage limit reached\"}}\n";

        var ex = Assert.Throws<HarnessException>(() => driver.Parse(events, scratch));
        Assert.Contains("usage limit reached", ex.Message);
    }
}
