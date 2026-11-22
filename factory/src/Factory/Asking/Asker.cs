using System.Diagnostics;
using Factory.Config;
using Factory.Drivers;

namespace Factory.Asking;

/// <summary>One answer, the same shape whichever harness gave it.</summary>
public sealed record AskResult(
    string Harness,
    string Model,
    string Text,
    long DurationMs,
    string SessionId = "",
    double? CostUsd = null,
    long? InputTokens = null,
    long? CachedInputTokens = null,
    long? OutputTokens = null);

/// <summary>Runs one prompt through one harness, headless, and returns the factory's own result shape.</summary>
public static class Asker
{
    /// <summary>
    /// Sends <paramref name="prompt"/> on stdin to one headless run and reads its answer.
    /// <paramref name="path"/> replaces PATH for the lookup and the run; tests use it to put fake harnesses first.
    /// </summary>
    public static async Task<AskResult> AskAsync(
        IDriver driver,
        string prompt,
        ModelChoice choice,
        string workingDirectory,
        TimeSpan timeout,
        string? path = null)
    {
        path ??= Environment.GetEnvironmentVariable("PATH") ?? "";
        var executable = ExecutableFinder.Find(driver.Executable, path)
            ?? throw new HarnessException(
                $"`{driver.Executable}` is not installed or not on PATH; see docs/factory/vps-setup.md");

        var scratch = Directory.CreateTempSubdirectory("factory-").FullName;
        try
        {
            var start = new ProcessStartInfo(executable)
            {
                WorkingDirectory = workingDirectory,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };
            foreach (var arg in driver.Arguments(choice, scratch))
            {
                start.ArgumentList.Add(arg);
            }
            start.Environment["PATH"] = path;

            var stopwatch = Stopwatch.StartNew();
            using var process = Process.Start(start)
                ?? throw new HarnessException($"{driver.Name} could not be started");

            // Read both streams while the program runs; waiting first can deadlock on a full pipe.
            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();
            await process.StandardInput.WriteAsync(prompt);
            process.StandardInput.Close();

            using var cancel = new CancellationTokenSource(timeout);
            try
            {
                await process.WaitForExitAsync(cancel.Token);
            }
            catch (OperationCanceledException)
            {
                process.Kill(entireProcessTree: true);
                throw new HarnessException($"{driver.Name} gave no answer within {timeout.TotalSeconds:0.##} s");
            }
            var duration = stopwatch.ElapsedMilliseconds;
            var output = await stdout;
            var errors = await stderr;

            if (process.ExitCode != 0)
            {
                var tail = Tail(errors.Length > 0 ? errors : output);
                throw new HarnessException($"{driver.Name} exited with code {process.ExitCode}: {tail}");
            }

            var reply = driver.Parse(output, scratch);
            return new AskResult(
                Harness: driver.Name,
                Model: FirstNonEmpty(reply.Model, choice.Model, "default"),
                Text: reply.Text,
                DurationMs: duration,
                SessionId: reply.SessionId,
                CostUsd: reply.CostUsd,
                InputTokens: reply.InputTokens,
                CachedInputTokens: reply.CachedInputTokens,
                OutputTokens: reply.OutputTokens);
        }
        finally
        {
            Directory.Delete(scratch, recursive: true);
        }
    }

    private static string FirstNonEmpty(params string[] values) => values.First(v => v.Length > 0);

    private static string Tail(string output, int limit = 400)
    {
        var text = string.Join(' ', output.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return text.Length <= limit ? text : "…" + text[^limit..];
    }
}

/// <summary>Finds a program on a PATH string, like the shell does.</summary>
public static class ExecutableFinder
{
    public static string? Find(string name, string path)
    {
        foreach (var dir in path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            var candidate = Path.Combine(dir, name);
            if (File.Exists(candidate) && IsExecutable(candidate))
            {
                return candidate;
            }
        }
        return null;
    }

    private static bool IsExecutable(string file) =>
        OperatingSystem.IsWindows()
        || (File.GetUnixFileMode(file) & (UnixFileMode.UserExecute | UnixFileMode.GroupExecute | UnixFileMode.OtherExecute)) != 0;
}
