using System.Text.Json;
using Azure.Connectors.Sdk.Office365.Models;

using var document = JsonDocument.Parse(File.ReadAllText(args[0]));
var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
const string prefix = "[connector-pivots]";
Office365OnNewEmailTriggerPayload? Parse(JsonElement data) =>
    data.Deserialize<Office365OnNewEmailTriggerPayload>(options);
var payload = Parse(document.RootElement.GetProperty("mixed"));
var ids = new List<string>();
var result = await Processing.ProcessAsync(payload, (id, _) =>
{
    ids.Add(id);
    return Task.CompletedTask;
}, prefix);
if (result != new ProcessingResult(3, 2) || !ids.SequenceEqual(["test-1", "test-2"]))
    throw new Exception("Prefix filtering failed");
var empty = await Processing.ProcessAsync(Parse(document.RootElement.GetProperty("empty")),
    (_, _) => throw new Exception("Unexpected action"), prefix);
if (empty != new ProcessingResult(0, 0)) throw new Exception("Empty batch failed");
foreach (var invalid in document.RootElement.GetProperty("invalid").EnumerateArray())
{
    try
    {
        await Processing.ProcessAsync(Parse(invalid),
            (_, _) => throw new Exception("Unexpected action"), prefix);
        throw new Exception("Invalid payload accepted");
    }
    catch (Exception ex) when (ex is JsonException or InvalidDataException) { }
}
try
{
    await Processing.ProcessAsync(payload, (_, _) => throw new Exception("Unexpected action"), "");
    throw new Exception("Empty prefix accepted");
}
catch (ArgumentException) { }
try
{
    await Processing.ProcessAsync(payload, (_, _) => throw new IOException("Action failed"), prefix);
    throw new Exception("Action failure acknowledged");
}
catch (IOException ex) when (ex.Message == "Action failed") { }
Console.WriteLine("All .NET payload, prefix, and action failure checks passed.");
