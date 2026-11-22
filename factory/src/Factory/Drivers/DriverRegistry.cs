namespace Factory.Drivers;

/// <summary>All harness drivers. Adding a harness means adding a driver here and an entry in models.json.</summary>
public static class DriverRegistry
{
    public static IReadOnlyDictionary<string, IDriver> All { get; } =
        new IDriver[] { new ClaudeDriver(), new CodexDriver() }.ToDictionary(d => d.Name);
}
