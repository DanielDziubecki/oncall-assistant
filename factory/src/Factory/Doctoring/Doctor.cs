using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Factory.Asking;

namespace Factory.Doctoring;

[JsonConverter(typeof(JsonStringEnumConverter<Status>))]
public enum Status
{
    Ok,
    Warn,
    Fail,
}

public sealed record Check(string Name, Status Status, string Detail, string Fix = "");

public sealed record CommandOutput(int Code, string Stdout, string Stderr)
{
    /// <summary>The first non-empty line, from stdout if it has one, else from stderr.</summary>
    public string FirstLine() =>
        new[] { Stdout, Stderr }
            .SelectMany(text => text.Split('\n'))
            .Select(line => line.Trim())
            .FirstOrDefault(line => line.Length > 0) ?? "";
}

/// <summary>Runs a command and returns its output, or null when the program is not installed.</summary>
public delegate CommandOutput? CommandRunner(IReadOnlyList<string> argv);

public sealed record Tool(string Name, string[] Argv, bool Required, string NeededFor, string Fix);

/// <summary>
/// Checks that this machine can run the factory: tools, harness logins, memory and disk.
/// It only runs version and login-status commands; it never calls a model.
/// </summary>
public static class Doctor
{
    public const string SetupGuide = "docs/factory/vps-setup.md";

    public static readonly Tool[] Tools =
    [
        new("git", ["git", "--version"], true, "everything", "sudo apt-get install -y git"),
        new("dotnet", ["dotnet", "--version"], true, "building the factory", $"see {SetupGuide}, step 5"),
        new("uv", ["uv", "--version"], true, "the Python projects", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
        new("docker", ["docker", "version", "--format", "{{.Server.Version}}"], true,
            "shopfront and the incident lab", $"see {SetupGuide}, step 4"),
        new("docker compose", ["docker", "compose", "version", "--short"], true,
            "shopfront and the incident lab", $"see {SetupGuide}, step 4"),
        new("gh", ["gh", "--version"], false, "pull requests from this machine", $"see {SetupGuide}, step 7"),
        new("hc", ["hc", "--version"], false, "the Herdr workspace from F1: Main and helper panes",
            "curl -fsSL https://releases.herdr.dev/core/install.sh | sh"),
        new("tmux", ["tmux", "-V"], false, "a fallback workspace where Herdr is not available",
            "sudo apt-get install -y tmux"),
    ];

    public static IReadOnlyList<Check> Diagnose(
        CommandRunner? run = null,
        string osRelease = "/etc/os-release",
        string memInfo = "/proc/meminfo",
        string? home = null)
    {
        run ??= RunCommand;
        var checks = new List<Check>
        {
            CheckOs(osRelease),
            CheckMemory(memInfo),
            CheckDisk(home ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile)),
        };
        checks.AddRange(Tools.Select(tool => CheckTool(tool, run)));
        var claude = CheckClaude(run);
        var codex = CheckCodex(run);
        checks.AddRange([claude, codex, CheckHarnesses(claude, codex)]);
        return checks;
    }

    public static Check CheckTool(Tool tool, CommandRunner run)
    {
        var output = run(tool.Argv);
        if (output is { Code: 0 })
        {
            return new Check(tool.Name, Status.Ok, output.FirstLine());
        }
        var problem = output is null ? "not installed" : NonEmpty(output.FirstLine(), "failed");
        return new Check(tool.Name, tool.Required ? Status.Fail : Status.Warn,
            $"{problem} (needed for {tool.NeededFor})", tool.Fix);
    }

    public static Check CheckClaude(CommandRunner run)
    {
        var version = run(["claude", "--version"]);
        if (version is not { Code: 0 })
        {
            return new Check("claude", Status.Warn, "Claude Code is not installed",
                $"see {SetupGuide}, step 2");
        }
        var auth = ReadClaudeAuth(run(["claude", "auth", "status", "--json"]));
        if (auth is not { LoggedIn: true })
        {
            return new Check("claude", Status.Warn, $"{version.FirstLine()}, not logged in",
                "run `claude` and log in with your subscription account");
        }
        return new Check("claude", Status.Ok,
            $"{version.FirstLine()}, logged in ({NonEmpty(auth.AuthMethod ?? "", "unknown method")})");
    }

    public static Check CheckCodex(CommandRunner run)
    {
        var version = run(["codex", "--version"]);
        if (version is not { Code: 0 })
        {
            return new Check("codex", Status.Warn, "Codex CLI is not installed", $"see {SetupGuide}, step 5");
        }
        var status = run(["codex", "login", "status"]);
        if (status is not { Code: 0 })
        {
            return new Check("codex", Status.Warn, $"{version.FirstLine()}, not logged in",
                "run `codex login --device-auth` and log in with your ChatGPT account");
        }
        return new Check("codex", Status.Ok, $"{version.FirstLine()}, {status.FirstLine()}");
    }

    public static Check CheckHarnesses(Check claude, Check codex)
    {
        var ready = new[] { claude, codex }.Where(c => c.Status == Status.Ok).Select(c => c.Name).ToList();
        return ready.Count == 0
            ? new Check("harness", Status.Fail, "no harness is installed and logged in, so `factory ask` can't run",
                "install and log in to Claude Code or Codex, ideally both")
            : new Check("harness", Status.Ok, $"ready: {string.Join(", ", ready)}");
    }

    public static Check CheckOs(string osRelease)
    {
        var name = File.Exists(osRelease)
            ? File.ReadLines(osRelease)
                .Where(line => line.StartsWith("PRETTY_NAME=", StringComparison.Ordinal))
                .Select(line => line["PRETTY_NAME=".Length..].Trim('"'))
                .FirstOrDefault()
            : null;
        return new Check("os", Status.Ok, name ?? "unknown (no /etc/os-release)");
    }

    public static Check CheckMemory(string memInfo, double warnBelowGib = 8)
    {
        long totalKib = 0;
        if (File.Exists(memInfo))
        {
            var line = File.ReadLines(memInfo).FirstOrDefault(l => l.StartsWith("MemTotal:", StringComparison.Ordinal));
            if (line is not null)
            {
                totalKib = long.Parse(line.Split(' ', StringSplitOptions.RemoveEmptyEntries)[1]);
            }
        }
        if (totalKib == 0)
        {
            return new Check("memory", Status.Warn, "unknown (no /proc/meminfo)");
        }
        var gib = totalKib / 1024.0 / 1024.0;
        return new Check("memory", gib < warnBelowGib ? Status.Warn : Status.Ok,
            $"{gib:0.0} GiB total; shopfront with stack A uses about 2 GiB");
    }

    public static Check CheckDisk(string path, double warnBelowGib = 20)
    {
        var freeGib = new DriveInfo(Path.GetFullPath(path)).AvailableFreeSpace / 1024.0 / 1024.0 / 1024.0;
        var low = freeGib < warnBelowGib;
        return new Check("disk", low ? Status.Warn : Status.Ok, $"{freeGib:0} GiB free in {path}",
            low ? "free space: Docker images and build caches need about 20 GiB" : "");
    }

    public static string Render(IReadOnlyList<Check> checks)
    {
        var width = checks.Max(c => c.Name.Length);
        var report = new StringBuilder();
        foreach (var check in checks)
        {
            report.AppendLine($"{Label(check.Status),-4}  {check.Name.PadRight(width)}  {check.Detail}");
            if (check.Fix.Length > 0 && check.Status != Status.Ok)
            {
                report.AppendLine($"{"",-4}  {"".PadRight(width)}  fix: {check.Fix}");
            }
        }
        var failures = checks.Count(c => c.Status == Status.Fail);
        var warnings = checks.Count(c => c.Status == Status.Warn);
        report.AppendLine();
        report.Append(failures > 0
            ? $"{failures} problem(s) to fix before the factory can run; {warnings} warning(s)."
            : $"Ready. {warnings} warning(s).");
        return report.ToString();
    }

    private static string Label(Status status) => status.ToString().ToLowerInvariant();

    private static string NonEmpty(string value, string fallback) => value.Length > 0 ? value : fallback;

    private static ClaudeAuth? ReadClaudeAuth(CommandOutput? output)
    {
        if (output is null)
        {
            return null;
        }
        try
        {
            return JsonSerializer.Deserialize<ClaudeAuth>(output.Stdout, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private sealed record ClaudeAuth(bool LoggedIn, string? AuthMethod);

    /// <summary>The real runner: finds the program on PATH and runs it with a 20 s limit.</summary>
    public static CommandOutput? RunCommand(IReadOnlyList<string> argv)
    {
        var executable = ExecutableFinder.Find(argv[0], Environment.GetEnvironmentVariable("PATH") ?? "");
        if (executable is null)
        {
            return null;
        }
        var start = new ProcessStartInfo(executable)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };
        foreach (var arg in argv.Skip(1))
        {
            start.ArgumentList.Add(arg);
        }
        try
        {
            using var process = Process.Start(start)!;
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(TimeSpan.FromSeconds(20)))
            {
                process.Kill(entireProcessTree: true);
                return new CommandOutput(-1, "", "timed out after 20 s");
            }
            return new CommandOutput(process.ExitCode, stdout.Result, stderr.Result);
        }
        catch (Exception ex) when (ex is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            return new CommandOutput(-1, "", ex.Message);
        }
    }
}
