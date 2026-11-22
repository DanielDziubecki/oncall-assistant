using System.Text.Json;
using Factory.Config;
using Factory.Doctoring;
using Factory.Drivers;

namespace Factory.Tests;

/// <summary>
/// Runs the command line in memory. The fake claude is found through PATH, so these tests change
/// the process environment and must not run in parallel with each other.
/// </summary>
[Collection(nameof(PathCollection))]
public sealed class CliTests : IDisposable
{
    private readonly Fakes fakes = new();
    private readonly string? originalPath = Environment.GetEnvironmentVariable("PATH");
    private readonly string fakeClaude;

    public CliTests()
    {
        fakeClaude = fakes.Write("claude", Fakes.Prints(Fakes.Fixture("claude-result.json")));
        Environment.SetEnvironmentVariable("PATH", fakes.Bin);
    }

    public void Dispose()
    {
        Environment.SetEnvironmentVariable("PATH", originalPath);
        fakes.Dispose();
    }

    private static (int Code, string Out, string Err) Run(string stdin, params string[] args)
    {
        var output = new StringWriter();
        var error = new StringWriter();
        var code = Cli.Run(args, new StringReader(stdin), output, error, workingDirectory: RepoRoot);
        return (code, output.ToString(), error.ToString());
    }

    /// <summary>The repo root, found the same way the tool finds models.json.</summary>
    private static string RepoRoot =>
        Path.GetDirectoryName(Path.GetDirectoryName(ModelsFile.Find(AppContext.BaseDirectory)!))!;

    [Fact]
    public void Ask_prints_the_answer()
    {
        var (code, output, _) = Run("", "ask", "--harness", "claude", "Is 7 prime?");

        Assert.Equal(0, code);
        Assert.Equal("OK", output.Trim());
    }

    [Fact]
    public void Ask_uses_the_configured_model_unless_overridden()
    {
        var configured = ModelsFile.Load(ModelsFile.Find(RepoRoot)!)["claude"].For(Size.Small).Model;

        Run("", "ask", "--harness", "claude", "hi");
        var configuredArgs = Fakes.RecordedArguments(fakeClaude);
        Run("", "ask", "--harness", "claude", "--model", "other-model", "hi");
        var overriddenArgs = Fakes.RecordedArguments(fakeClaude);

        Assert.Equal(configured, ClaudeDriverTests.After(configuredArgs, "--model"));
        Assert.Equal("other-model", ClaudeDriverTests.After(overriddenArgs, "--model"));
    }

    [Fact]
    public void Ask_json_prints_the_whole_result()
    {
        var (_, output, _) = Run("", "ask", "--harness", "claude", "--json", "hi");

        using var result = JsonDocument.Parse(output);
        Assert.Equal("claude", result.RootElement.GetProperty("harness").GetString());
        Assert.Equal("OK", result.RootElement.GetProperty("text").GetString());
        Assert.Equal(649, result.RootElement.GetProperty("cached_input_tokens").GetInt64());
    }

    [Fact]
    public void Ask_reads_the_prompt_from_stdin()
    {
        var (code, output, _) = Run("Summarize: retries need idempotency keys.", "ask", "--harness", "claude");

        Assert.Equal(0, code);
        Assert.Equal("OK", output.Trim());
        Assert.Equal("Summarize: retries need idempotency keys.", Fakes.RecordedStdin(fakeClaude));
    }

    [Fact]
    public void An_empty_prompt_is_refused()
    {
        var (code, _, error) = Run("", "ask", "--harness", "claude", "  ");

        Assert.Equal(2, code);
        Assert.Contains("empty", error);
    }

    [Fact]
    public void A_harness_error_exits_1_with_the_reason()
    {
        var (code, _, error) = Run("", "ask", "--harness", "codex", "hi");

        Assert.Equal(1, code);
        Assert.Contains("`codex` is not installed", error);
    }

    [Fact]
    public void An_unknown_harness_is_refused()
    {
        var (code, _, _) = Run("", "ask", "--harness", "gemini", "hi");

        Assert.NotEqual(0, code);
    }

    [Fact]
    public void Every_driver_has_models_in_models_json()
    {
        var models = ModelsFile.Load(ModelsFile.Find(RepoRoot)!);

        Assert.All(DriverRegistry.All.Keys, name => Assert.True(models.ContainsKey(name), $"{name} is missing"));
    }

    [Fact]
    public void Doctor_exits_1_when_a_check_fails()
    {
        Check[] checks = [new("git", Status.Ok, "git version 2.43.0"), new("docker", Status.Fail, "not installed", "see the guide")];
        var output = new StringWriter();

        var code = Cli.Run(["doctor", "--json"], new StringReader(""), output, new StringWriter(), () => checks);

        Assert.Equal(1, code);
        using var printed = JsonDocument.Parse(output.ToString());
        Assert.Equal(["Ok", "Fail"], printed.RootElement.EnumerateArray().Select(c => c.GetProperty("status").GetString()));
    }
}

[CollectionDefinition(nameof(PathCollection), DisableParallelization = true)]
public sealed class PathCollection;
