from collections.abc import Iterator

import httpx


def iter_sse_data(response: httpx.Response) -> Iterator[str]:
    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data and data != "[DONE]":
            yield data
