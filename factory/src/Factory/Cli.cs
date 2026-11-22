using System.CommandLine;
using System.Text.Json;
using Factory.Asking;
using Factory.Config;
using Factory.Doctoring;
using Factory.Drivers;

namespace Factory;

/// <summary>The <c>factory</c> command line: ask a harness one question, or check this machine.</summary>
public static class Cli
{
    public static readonly JsonSerializerOptions Json = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        WriteIndented = true,
    };

    public static int Run(
        string[] args,
        TextReader input,
        TextWriter output,
        TextWriter error,
        Func<IReadOnlyList<Check>>? diagnose = null,
        string? workingDirectory = null)
    {
        var root = new RootCommand("Development factory: runs Claude Code and Codex as interchangeable workers.");
        root.Subcommands.Add(AskCommand(input, output, error, workingDirectory ?? Directory.GetCurrentDirectory()));
        root.Subcommands.Add(DoctorCommand(output, diagnose ?? (() => Doctor.Diagnose())));
        return root.Parse(args).Invoke(new InvocationConfiguration { Output = output, Error = error });
    }

    private static Command AskCommand(TextReader input, TextWriter output, TextWriter error, string workingDirectory)
    {
        var prompt = new Argument<string>("prompt")
        {
            Description = "The question; '-' or nothing reads it from stdin.",
            DefaultValueFactory = _ => "-",
        };
        var harness = new Option<string>("--harness") { Description = "Which harness answers.", Required = true };
        harness.AcceptOnlyFromAmong([.. DriverRegistry.All.Keys.Order()]);
        var size = new Option<Size>("--size")
        {
            Description = "small for helper work, large for hard work.",
            DefaultValueFactory = _ => Size.Small,
        };
        var model = new Option<string?>("--model") { Description = "Use this model for this run only." };
        var effort = new Option<string?>("--effort") { Description = "Use this effort level for this run only." };
        var timeout = new Option<double>("--timeout")
        {
            Description = "Seconds to wait for the answer.",
            DefaultValueFactory = _ => 300,
        };
        var json = new Option<bool>("--json") { Description = "Print the whole result: text, model, time, tokens, cost." };

        var command = new Command(
            "ask",
            "Ask one harness one question, headless and without tools. The run loads none of the project's "
            + "instructions, skills or hooks: its only context is the prompt. The model comes from "
            + "factory/models.json for the chosen size.")
        {
            prompt, harness, size, model, effort, timeout, json,
        };
        command.SetAction(result =>
        {
            var text = result.GetValue(prompt) is "-" or null ? input.ReadToEnd() : result.GetValue(prompt)!;
            if (string.IsNullOrWhiteSpace(text))
            {
                error.WriteLine("factory ask: the prompt is empty");
                return 2;
            }

            var driver = DriverRegistry.All[result.GetValue(harness)!];
            var choice = ConfiguredChoice(driver.Name, result.GetValue(size), workingDirectory);
            choice = choice with
            {
                Model = result.GetValue(model) ?? choice.Model,
                Effort = result.GetValue(effort) ?? choice.Effort,
            };

            try
            {
                var answer = Asker.AskAsync(driver, text, choice, workingDirectory,
                    TimeSpan.FromSeconds(result.GetValue(timeout))).GetAwaiter().GetResult();
                output.WriteLine(result.GetValue(json) ? JsonSerializer.Serialize(answer, Json) : answer.Text);
                return 0;
            }
            catch (HarnessException ex)
            {
                error.WriteLine($"factory ask: {ex.Message}");
                return 1;
            }
        });
        return command;
    }

    private static Command DoctorCommand(TextWriter output, Func<IReadOnlyList<Check>> diagnose)
    {
        var json = new Option<bool>("--json") { Description = "Print the checks as JSON." };
        var command = new Command(
            "doctor", "Check this machine: tools, harness logins, memory and disk. Never calls a model.")
        {
            json,
        };
        command.SetAction(result =>
        {
            var checks = diagnose();
            output.WriteLine(result.GetValue(json) ? JsonSerializer.Serialize(checks, Json) : Doctor.Render(checks));
            return checks.Any(c => c.Status == Status.Fail) ? 1 : 0;
        });
        return command;
    }

    private static ModelChoice ConfiguredChoice(string harness, Size size, string workingDirectory)
    {
        var file = ModelsFile.Find(workingDirectory);
        if (file is null)
        {
            return new ModelChoice();
        }
        return ModelsFile.Load(file).TryGetValue(harness, out var models) ? models.For(size) : new ModelChoice();
    }
}
