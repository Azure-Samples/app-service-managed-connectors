using System.Text.Json;
using Azure.Connectors.Sdk;
using Azure.Connectors.Sdk.Office365;
using Azure.Connectors.Sdk.Office365.Models;
using Azure.Identity;

var builder = WebApplication.CreateBuilder(args);
string Required(string name) => !string.IsNullOrWhiteSpace(builder.Configuration[name])
    ? builder.Configuration[name]!
    : throw new InvalidOperationException($"Missing required setting: {name}");

var runtimeUrl = new Uri(Required("OFFICE365_CONNECTION_RUNTIME_URL"));
if (runtimeUrl.Scheme != Uri.UriSchemeHttps)
    throw new InvalidOperationException("Connection URL must use HTTPS.");
var prefix = Required("TEST_SUBJECT_PREFIX");
var credential = new ManagedIdentityCredential(
    ManagedIdentityId.FromUserAssignedClientId(Required("AZURE_CLIENT_ID")));
builder.Services.AddSingleton(new Office365Client(runtimeUrl, credential));

var app = builder.Build();
app.MapGet("/healthz", () => Results.Ok(new { status = "healthy" }));
app.MapPost("/api/webhook", async (
    HttpRequest request, Office365Client client, ILoggerFactory loggerFactory,
    CancellationToken cancellationToken) =>
{
    var logger = loggerFactory.CreateLogger("ConnectorWebhook");
    try
    {
        var payload = await request.ReadFromJsonAsync<Office365OnNewEmailTriggerPayload>(
            new JsonSerializerOptions(JsonSerializerDefaults.Web), cancellationToken);
        var result = await Processing.ProcessAsync(payload, async (id, token) =>
        {
            await client.FlagAsync(
                messageId: id,
                input: new UpdateEmailFlag { Flag = new { flagStatus = "flagged" } },
                originalMailboxAddress: null,
                cancellationToken: token);
        }, prefix, cancellationToken);
        logger.LogInformation("connector_processed received={Received} flagged={Flagged}",
            result.Received, result.Flagged);
        return Results.Ok(result);
    }
    catch (Exception ex) when (ex is JsonException or InvalidDataException)
    {
        logger.LogWarning("Invalid connector payload: {Type}", ex.GetType().Name);
        return Results.BadRequest(new { error = "Invalid connector payload" });
    }
    catch (ConnectorException ex)
    {
        logger.LogError("Connector action failed: {Type}", ex.GetType().Name);
        return Results.Json(new { error = "Connector action failed" }, statusCode: 502);
    }
});
app.Run();
