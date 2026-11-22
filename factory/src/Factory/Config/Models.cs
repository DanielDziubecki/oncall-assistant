using System.Text.Json;

namespace Factory.Config;

/// <summary>What a factory job asks for instead of a model.</summary>
public enum Size
{
    Small,
    Large,
}

/// <summary>A model and an effort level for one harness. Empty means the harness's own default.</summary>
public sealed record ModelChoice(string Model = "", string Effort = "");

public sealed record HarnessModels(ModelChoice? Small = null, ModelChoice? Large = null)
{
    public ModelChoice For(Size size) => (size == Size.Small ? Small : Large) ?? new ModelChoice();
}

/// <summary>
/// Reads factory/models.json: which model each harness uses for each size of job.
/// Jobs ask for a size, so switching models never touches a job's definition.
/// </summary>
public static class ModelsFile
{
    public const string RelativePath = "factory/models.json";

    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = true,
    };

    public static IReadOnlyDictionary<string, HarnessModels> Load(string path) =>
        JsonSerializer.Deserialize<Dictionary<string, HarnessModels>>(File.ReadAllText(path), Options)
        ?? throw new InvalidDataException($"{path} is empty");

    /// <summary>
    /// Finds factory/models.json by walking up from <paramref name="start"/>, the way git finds .git.
    /// Returns null outside a repo that has one; every harness then uses its own defaults.
    /// </summary>
    public static string? Find(string start)
    {
        for (var dir = new DirectoryInfo(start); dir is not null; dir = dir.Parent)
        {
            var candidate = Path.Combine(dir.FullName, RelativePath);
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }
        return null;
    }
}
