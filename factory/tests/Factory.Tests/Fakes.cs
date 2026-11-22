namespace Factory.Tests;

/// <summary>
/// Fake harness programs: tiny shell scripts in a temporary folder that you use as PATH.
/// Each fake saves the arguments and stdin it got next to itself, then runs a short body,
/// usually one that prints a recorded answer. Nothing calls a real model.
///
/// Fixtures/claude-result.json is a recorded <c>claude -p</c> result with the model name and
/// ids replaced. Fixtures/codex-exec.synthetic.jsonl is synthetic: written from the documented
/// event names, not recorded. Replace it with a recorded run once Codex runs on the VPS.
/// </summary>
public sealed class Fakes : IDisposable
{
    public static string Fixture(string name) => Path.Combine(AppContext.BaseDirectory, "Fixtures", name);

    public string Bin { get; } = Directory.CreateTempSubdirectory("factory-fakes-").FullName;

    /// <summary>Writes an executable called <paramref name="name"/> that records its input, then runs <paramref name="body"/>.</summary>
    public string Write(string name, string body)
    {
        if (OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException("Fake harnesses are shell scripts; run the tests on Linux or macOS.");
        }
        var path = Path.Combine(Bin, name);
        File.WriteAllText(path,
            "#!/bin/sh\n"
            + $"for a in \"$@\"; do printf '%s\\n' \"$a\"; done > '{path}.argv'\n"
            + $"/bin/cat > '{path}.stdin'\n"
            + body);
        File.SetUnixFileMode(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        return path;
    }

    public static string Prints(string file) => $"/bin/cat '{file}'\n";

    /// <summary>Writes <paramref name="answer"/> where --output-last-message points, then prints the events.</summary>
    public static string CodexAnswers(string answer, string events) =>
        "out=''; prev=''\n"
        + "for a in \"$@\"; do [ \"$prev\" = '--output-last-message' ] && out=\"$a\"; prev=\"$a\"; done\n"
        + $"printf '%s\\n' '{answer}' > \"$out\"\n"
        + Prints(events);

    public static string Fails(int code, string message) => $"printf '%s' '{message}' >&2\nexit {code}\n";

    public static string Hangs(int seconds) => $"/bin/sleep {seconds}\n";

    public static IReadOnlyList<string> RecordedArguments(string fake) =>
        File.ReadAllText(fake + ".argv").Split('\n')[..^1];

    public static string RecordedStdin(string fake) => File.ReadAllText(fake + ".stdin");

    public void Dispose() => Directory.Delete(Bin, recursive: true);
}
