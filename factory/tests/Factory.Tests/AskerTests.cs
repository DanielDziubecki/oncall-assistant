using Factory.Asking;
using Factory.Config;
using Factory.Drivers;

namespace Factory.Tests;

public sealed class AskerTests : IDisposable
{
    private readonly Fakes fakes = new();
    private readonly string workDir = Directory.CreateTempSubdirectory("factory-work-").FullName;

    public void Dispose()
    {
        fakes.Dispose();
        Directory.Delete(workDir, recursive: true);
    }

    private Task<AskResult> Ask(IDriver driver, string prompt, ModelChoice? choice = null, double timeoutSeconds = 30) =>
        Asker.AskAsync(driver, prompt, choice ?? new ModelChoice(), workDir, TimeSpan.FromSeconds(timeoutSeconds), fakes.Bin);

    [Fact]
    public async Task Claude_gets_the_prompt_on_stdin_and_the_driver_flags()
    {
        var fake = fakes.Write("claude", Fakes.Prints(Fakes.Fixture("claude-result.json")));
        var choice = new ModelChoice("haiku");

        var result = await Ask(new ClaudeDriver(), "Is 7 prime?", choice);

        Assert.Equal("claude", result.Harness);
        Assert.Equal("OK", result.Text);
        Assert.Equal("example-small-model", result.Model);
        Assert.Equal("Is 7 prime?", Fakes.RecordedStdin(fake));
        Assert.Equal(new ClaudeDriver().Arguments(choice, "unused"), Fakes.RecordedArguments(fake));
        Assert.DoesNotContain("Is 7 prime?", Fakes.RecordedArguments(fake));
    }

    [Fact]
    public async Task Codex_answer_comes_from_its_last_message_file()
    {
        var fake = fakes.Write("codex", Fakes.CodexAnswers("OK", Fakes.Fixture("codex-exec.synthetic.jsonl")));

        var result = await Ask(new CodexDriver(), "Is 7 prime?");

        Assert.Equal("codex", result.Harness);
        Assert.Equal("OK", result.Text);
        Assert.Equal("default", result.Model);
        Assert.Equal(5, result.OutputTokens);
        Assert.Equal("Is 7 prime?", Fakes.RecordedStdin(fake));
    }

    [Fact]
    public async Task A_missing_harness_says_how_to_install_it()
    {
        var ex = await Assert.ThrowsAsync<HarnessException>(() => Ask(new CodexDriver(), "hi"));

        Assert.Contains("`codex` is not installed", ex.Message);
        Assert.Contains("vps-setup.md", ex.Message);
    }

    [Fact]
    public async Task A_failed_run_reports_its_exit_code_and_stderr()
    {
        fakes.Write("claude", Fakes.Fails(3, "Not logged in. Run /login."));

        var ex = await Assert.ThrowsAsync<HarnessException>(() => Ask(new ClaudeDriver(), "hi"));

        Assert.Contains("exited with code 3: Not logged in. Run /login.", ex.Message);
    }

    [Fact]
    public async Task A_run_that_takes_too_long_is_stopped()
    {
        fakes.Write("claude", Fakes.Hangs(10));

        var ex = await Assert.ThrowsAsync<HarnessException>(() => Ask(new ClaudeDriver(), "hi", timeoutSeconds: 0.5));

        Assert.Contains("no answer within 0.5 s", ex.Message);
    }
}
