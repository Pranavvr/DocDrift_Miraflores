# retry-client

A minimal HTTP client with automatic retries.

## Retries

The client retries 3 times, waiting 2 seconds between attempts.

## Usage

Call `client.get(url)` and handle `ClientError` for failed requests.
