using Azure.Connectors.Sdk.Office365.Models;

public static class Processing
{
    public static async Task<ProcessingResult> ProcessAsync(
        Office365OnNewEmailTriggerPayload? payload,
        Func<string, CancellationToken, Task> flagEmail,
        string prefix,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(prefix);
        var emails = payload?.Body?.Value;
        if (emails is null || emails.Any(email =>
            email is null || string.IsNullOrWhiteSpace(email.MessageId) || email.Subject is null))
        {
            throw new InvalidDataException("Expected body.value with email IDs and subjects.");
        }

        var flagged = 0;
        foreach (var email in emails)
        {
            if (!email.Subject!.StartsWith(prefix, StringComparison.Ordinal)) continue;
            await flagEmail(email.MessageId!, cancellationToken);
            flagged++;
        }
        return new ProcessingResult(emails.Count, flagged);
    }
}

public record ProcessingResult(int Received, int Flagged);
