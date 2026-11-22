using Factory.Doctoring;

namespace Factory.Tests;

public sealed class DoctorTests : IDisposable
{
    private const string ClaudeLoggedIn = "{\"loggedIn\": true, \"authMethod\": \"oauth_token\", \"configDirectory\": \"/x\"}";
    private readonly string dir = Directory.CreateTempSubdirectory("doctor-test-").FullName;

    public void Dispose() => Directory.Delete(dir, recursive: true);

    /// <summary>A fake machine: answers commands from a table; a missing program returns null.</summary>
    private static Dictionary<string, CommandOutput> ReadyMachine()
    {
        var answers = Doctor.Tools.ToDictionary(t => Key(t.Argv), t => new CommandOutput(0, $"{t.Name} 1.0\n", ""));
        answers[Key("claude", "--version")] = new(0, "2.1.330 (Claude Code)\n", "");
        answers[Key("claude", "auth", "status", "--json")] = new(0, ClaudeLoggedIn, "");
        answers[Key("codex", "--version")] = new(0, "codex-cli 0.171.0\n", "");
        answers[Key("codex", "login", "status")] = new(0, "Logged in using ChatGPT\n", "");
        return answers;
    }

    private static string Key(params IEnumerable<string> argv) => string.Join(' ', argv);

    private Dictionary<string, Check> Diagnose(Dictionary<string, CommandOutput> answers)
    {
        var memInfo = Path.Combine(dir, "meminfo");
        File.WriteAllText(memInfo, "MemTotal:       16384000 kB\nMemFree:         1000 kB\n");
        var osRelease = Path.Combine(dir, "os-release");
        File.WriteAllText(osRelease, "NAME=\"Ubuntu\"\nPRETTY_NAME=\"Ubuntu 24.04.3 LTS\"\n");
        return Doctor.Diagnose(argv => answers.GetValueOrDefault(Key(argv)), osRelease, memInfo, dir)
            .ToDictionary(c => c.Name);
    }

    [Fact]
    public void A_ready_machine_has_no_failures()
    {
        var checks = Diagnose(ReadyMachine());

        Assert.DoesNotContain(checks.Values, c => c.Status == Status.Fail);
        Assert.Equal("Ubuntu 24.04.3 LTS", checks["os"].Detail);
        Assert.StartsWith("15.6 GiB total", checks["memory"].Detail);
        Assert.Equal("2.1.330 (Claude Code), logged in (oauth_token)", checks["claude"].Detail);
        Assert.Equal("codex-cli 0.171.0, Logged in using ChatGPT", checks["codex"].Detail);
        Assert.Equal("ready: claude, codex", checks["harness"].Detail);
    }

    [Fact]
    public void A_missing_required_tool_fails()
    {
        var answers = ReadyMachine();
        answers.Remove(Key("docker", "version", "--format", "{{.Server.Version}}"));

        var docker = Diagnose(answers)["docker"];

        Assert.Equal(Status.Fail, docker.Status);
        Assert.StartsWith("not installed", docker.Detail);
    }

    [Fact]
    public void Docker_without_access_to_its_daemon_fails_with_the_reason()
    {
        var answers = ReadyMachine();
        answers[Key("docker", "version", "--format", "{{.Server.Version}}")] =
            new(1, "", "permission denied while trying to connect to the docker API\n");

        var docker = Diagnose(answers)["docker"];

        Assert.Equal(Status.Fail, docker.Status);
        Assert.StartsWith("permission denied", docker.Detail);
    }

    [Fact]
    public void A_missing_optional_tool_only_warns()
    {
        var answers = ReadyMachine();
        answers.Remove(Key("hc", "--version"));

        Assert.Equal(Status.Warn, Diagnose(answers)["hc"].Status);
    }

    [Fact]
    public void One_logged_in_harness_is_enough()
    {
        var answers = ReadyMachine();
        answers[Key("codex", "login", "status")] = new(1, "Not logged in\n", "");

        var checks = Diagnose(answers);

        Assert.Equal(Status.Warn, checks["codex"].Status);
        Assert.Equal("codex-cli 0.171.0, not logged in", checks["codex"].Detail);
        Assert.Equal("ready: claude", checks["harness"].Detail);
    }

    [Fact]
    public void No_logged_in_harness_fails()
    {
        var answers = ReadyMachine();
        answers[Key("claude", "auth", "status", "--json")] = new(1, "{\"loggedIn\": false}", "");
        answers.Remove(Key("codex", "--version"));

        var checks = Diagnose(answers);

        Assert.Equal(Status.Warn, checks["claude"].Status);
        Assert.Equal("Codex CLI is not installed", checks["codex"].Detail);
        Assert.Equal(Status.Fail, checks["harness"].Status);
    }

    [Fact]
    public void The_report_shows_fixes_for_problems_only()
    {
        var answers = ReadyMachine();
        answers.Remove(Key("git", "--version"));

        var report = Doctor.Render([.. Diagnose(answers).Values]);

        Assert.Contains("fail  git", report);
        Assert.Contains("fix: sudo apt-get install -y git", report);
        Assert.DoesNotContain("fix: curl -LsSf https://astral.sh/uv/install.sh", report);
        Assert.StartsWith("1 problem(s) to fix", report.Split('\n')[^1]);
    }
}
