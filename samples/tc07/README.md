# page-fetcher

Download web pages from scripts.

## Fetching pages

`fetch(url)` downloads a page and returns its text. Requests wait as long as the
server takes to respond, so slow servers never cause an error.
