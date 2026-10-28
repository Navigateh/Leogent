# Milestone 2：模型 Provider

Milestone 2 解决的问题是：Agent 不应该直接理解 OpenAI、Anthropic 或某个本地模型的响应格式。Runtime 只认识 Leogent 自己的 `ModelRequest` 和 `ModelResponse`，Provider 负责在两种协议之间转换。

完整流程如下：

```text
用户 Prompt
  → ModelRequest
  → Provider 转换成本厂商 JSON
  → HTTP/SSE
  → Provider 归一化成 ModelResponse / ModelChunk
  → CLI 或后续 Agent Loop
```

这一阶段还没有 Agent Loop。`leogent run` 只发送一次请求，不执行返回的工具调用。

## 1. Provider 协议

`ModelProvider` 是 Runtime 依赖的最小接口。上层不需要知道 HTTP、API Key 或厂商 SDK。

```python
class ModelProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> ModelCapabilities: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> Iterator[ModelChunk]: ...

    def close(self) -> None: ...
```

这段代码定义了两种调用方式和两种生命周期操作：

- `complete` 一次性取得完整响应。
- `stream` 按 chunk 返回文本和最终工具调用。
- `capabilities` 告诉 Runtime 模型是否支持工具、流和上下文窗口。
- `close` 释放 Provider 自己创建的 HTTP 连接。

Provider 使用 `Protocol` 而不是公共基类，因此实现类只需要满足接口，不需要继承一个庞大的框架类。

## 2. Capabilities 与统一 Chunk

模型之间的能力不同，Runtime 不能假设所有模型都支持相同特性。

```python
class ModelCapabilities(DomainModel):
    context_window: int | None = Field(default=None, gt=0)
    supports_native_tools: bool = True
    supports_streaming: bool = True
    supports_structured_output: bool = False
    supports_prompt_cache: bool = False
    tokenizer: str | None = None


class ModelChunk(DomainModel):
    text_delta: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: Usage | None = None
```

`capabilities` 不是装饰性元数据。它让 CLI 决定能否流式输出，也让后续 ReAct Runtime 决定使用 native tools 还是 JSON Action 降级。

`ModelChunk` 把流式输出压缩成两种关键信息：文本增量 `text_delta` 和最终工具调用 `tool_calls`。最后一个 chunk 还会包含结束原因和 usage。

## 3. 上下文预算校验

Provider 在发出网络请求前检查输入和输出预算。

```python
def validate_request(request: ModelRequest, capabilities: ModelCapabilities) -> None:
    context_window = capabilities.context_window
    if context_window is None:
        return
    requested_tokens = request.estimated_input_tokens + request.parameters.max_output_tokens
    if requested_tokens > context_window:
        raise ContextWindowExceeded(
            f"Request needs {requested_tokens} tokens but context window is {context_window}"
        )
```

`estimated_input_tokens` 暂时由调用方提供，Milestone 6 的 ContextBuilder 会用正式 token 估算器填充。这里先建立 Provider 边界：超出预算时，请求在本地失败，不浪费一次远程调用。

## 4. OpenAI-compatible 请求转换

OpenAI-compatible Provider 同时服务云端和本地 vLLM、Ollama、LM Studio 等服务。

```python
def _message_payload(message: Message) -> dict[str, object]:
    payload: dict[str, object] = {"role": message.role.value}
    if message.content is not None or message.role is MessageRole.ASSISTANT:
        payload["content"] = message.content
    if message.name is not None:
        payload["name"] = message.name
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, separators=(",", ":")),
                },
            }
            for call in message.tool_calls
        ]
    return payload
```

这段代码完成三个转换：

1. Leogent 的枚举 role 转成字符串。
2. Assistant 的结构化工具调用转成 OpenAI `tool_calls`。
3. 工具参数从字典重新序列化为 JSON 字符串，因为 OpenAI-compatible API 使用字符串表达 function arguments。

工具定义也使用相同边界：

```python
def _tool_payload(tool: ToolDefinition) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }
```

`input_schema` 原样传给模型服务，因此 MCP 提供的 JSON Schema 不需要在 Runtime 中复制一份。

生成参数由 `GenerationParameters` 控制：

```python
payload: dict[str, object] = {
    "model": self._config.model,
    "messages": [_message_payload(message) for message in request.messages],
    "temperature": request.parameters.temperature,
    "top_p": request.parameters.top_p,
    "max_tokens": request.parameters.max_output_tokens,
    "stream": stream,
}
```

这里使用 `max_tokens` 是为了兼容更多本地 OpenAI-compatible 服务。不同服务对生成参数的支持并不完全一致，因此 Provider 是记录这种差异的正确位置。

## 5. OpenAI-compatible 响应归一化

网络返回的 JSON 先由私有 Pydantic 模型校验，再转换成 Leogent 领域模型。

```python
try:
    envelope = _OpenAIEnvelope.model_validate_json(response.content)
except ValidationError as error:
    raise ProviderError("OpenAI-compatible returned an invalid response") from error
if not envelope.choices:
    raise ProviderError("OpenAI-compatible response did not contain a choice")
choice = envelope.choices[0]
return ModelResponse(
    content=choice.message.content,
    tool_calls=tuple(self._normalize_tool_call(call) for call in choice.message.tool_calls),
    finish_reason=choice.finish_reason,
    usage=Usage(
        input_tokens=envelope.usage.prompt_tokens,
        output_tokens=envelope.usage.completion_tokens,
    ),
)
```

核心转换是：

| Provider 字段 | Leogent 字段 |
| --- | --- |
| `message.content` | `ModelResponse.content` |
| `tool_calls` | `ModelResponse.tool_calls` |
| `finish_reason` | `finish_reason` |
| `prompt_tokens` | `Usage.input_tokens` |
| `completion_tokens` | `Usage.output_tokens` |

工具参数还需要从 JSON 字符串解析：

```python
def _parse_tool_arguments(value: str) -> dict[str, JsonValue]:
    if not value.strip():
        return {}
    try:
        parsed: object = json.loads(value)
    except json.JSONDecodeError as error:
        raise ProviderError("OpenAI-compatible tool arguments must be valid JSON") from error
    if not isinstance(parsed, dict):
        raise ProviderError("OpenAI-compatible tool arguments must be a JSON object")
    return cast(dict[str, JsonValue], parsed)
```

模型输出的工具参数并不可信。这里要求它必须是 JSON object，否则转换为统一的 `ProviderError`，避免后续 ToolRegistry 收到损坏的数据。

## 6. OpenAI-compatible 流式解析

SSE 的每一行可能是 `data: {...}`，也可能与请求无关。

```python
def iter_sse_data(response: httpx.Response) -> Iterator[str]:
    for line in response.iter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data and data != "[DONE]":
            yield data
```

文本 delta 可以立即显示：

```python
for choice in event.choices:
    if choice.delta.content:
        yield ModelChunk(text_delta=choice.delta.content)
```

工具调用则可能被拆成多个片段。Provider 按 `index` 累积 ID、函数名和 arguments：

```python
fragment = fragments.setdefault(
    tool_call.index,
    {"id": "", "name": "", "arguments": ""},
)
if tool_call.id:
    fragment["id"] += tool_call.id
if tool_call.function.name:
    fragment["name"] += tool_call.function.name
if tool_call.function.arguments:
    fragment["arguments"] += tool_call.function.arguments
```

直到流结束才解析 JSON：

```python
tool_calls = tuple(
    ToolCall(
        id=fragment["id"],
        name=fragment["name"],
        arguments=_parse_tool_arguments(fragment["arguments"]),
    )
    for _, fragment in sorted(fragments.items())
)
```

这样不会把半个 JSON 当成完整工具调用，也不会在文本流中提前泄漏未完成的参数。

## 7. Anthropic 的 Content Block

Anthropic Messages API 使用 content blocks，而不是 OpenAI 的 message fields。

```python
def _message_payload(message: Message) -> dict[str, object] | None:
    if message.role is MessageRole.SYSTEM:
        return None
    if message.role is MessageRole.TOOL:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content or "",
                }
            ],
        }
    if message.role is MessageRole.ASSISTANT:
        return {"role": "assistant", "content": _assistant_content(message)}
    return {"role": "user", "content": message.content or ""}
```

关键差异有三个：

- System message 最终作为请求顶层 `system` 字段。
- Tool result 要变成 user message 内的 `tool_result` block。
- Assistant tool call 要变成 `tool_use` block。

Assistant block 转换如下：

```python
def _assistant_content(message: Message) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    blocks.extend(
        {
            "type": "tool_use",
            "id": call.id,
            "name": call.name,
            "input": call.arguments,
        }
        for call in message.tool_calls
    )
    if not blocks:
        raise ProviderError("Anthropic assistant messages require content or tool calls")
    return blocks
```

这保证后续 ReAct Loop 可以把 `assistant(tool_use) → tool(tool_result)` 这样的历史重新发送给模型。

Anthropic 响应使用相反方向的转换：

```python
text = "".join(block.text or "" for block in envelope.content if block.type == "text")
tool_calls = tuple(
    ToolCall(
        id=block.id or "",
        name=block.name or "",
        arguments=block.input,
    )
    for block in envelope.content
    if block.type == "tool_use"
)
```

无论 Provider 返回 text block 还是 tool_use block，上层看到的都是同一种 `ModelResponse`。

## 8. HTTP 错误与密钥保护

所有 HTTP 错误都归一化为 `ProviderError`。

```python
def error_from_response(
    provider_name: str,
    response: Response,
    secret: str | None,
) -> ProviderError:
    body = redact(response.text[:1000].strip(), secret)
    detail = f": {body}" if body else ""
    return ProviderError(
        f"{provider_name} returned HTTP {response.status_code}{detail}",
        retryable=retryable_status(response.status_code),
        status_code=response.status_code,
    )
```

错误响应体在进入异常文本前会替换掉 API Key。`retryable_status` 把超时、限流和 5xx 标为可重试，但 Milestone 2 只记录 `retryable`，真正的重试策略留给后续 Runtime。

密钥只从环境变量读取：

```python
def resolve_api_key(
    profile: ProviderConfig,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    if isinstance(profile, TransformersProviderConfig):
        return None
    if profile.api_key_env is None:
        return None
    environment = os.environ if environ is None else environ
    value = environment.get(profile.api_key_env)
    return value or None
```

配置 JSON 中只有 `api_key_env` 的名称，没有真实密钥。

## 9. ScriptedProvider

Agent 算法测试不能每次都调用真实模型。`ScriptedProvider` 按顺序返回预先准备的响应，并记录收到的标准请求。

```python
class ScriptedProvider:
    def __init__(
        self,
        responses: Sequence[ModelResponse | Exception],
        *,
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        self._responses = list(responses)
        self._capabilities = capabilities or ModelCapabilities(context_window=8192)
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if not self._responses:
            raise ProviderError("Scripted provider responses are exhausted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
```

这使 Milestone 5 的 ReAct 测试可以精确描述“模型第一次调用工具，第二次给出答案”，默认测试不需要网络和密钥。

## 10. HTTPX MockTransport 测试

HTTP Provider 测试使用真实 HTTPX 请求对象，只替换网络传输层：

```python
def handler(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer secret-key"
    assert payload["model"] == "test-model"
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {"content": "Done"},
                    "finish_reason": "stop",
                }
            ]
        },
    )


client = httpx.Client(transport=httpx.MockTransport(handler))
```

这里测试的是 Provider 实际生成的 URL、Header 和 JSON payload，而不是一个伪造的 Provider 方法。这样修改请求转换逻辑时，测试能真正失败。

## 11. Provider Factory

Factory 根据配置类型创建具体实现。

```python
def create_provider(
    config: AppConfig,
    provider_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> ModelProvider:
    selected_name = provider_name or config.default_provider
    try:
        profile = config.providers[selected_name]
    except KeyError:
        raise ConfigurationError(f"Provider '{selected_name}' is not configured") from None
    environment = os.environ if environ is None else environ
    api_key = resolve_api_key(profile, environment)
    if isinstance(profile, OpenAICompatibleProviderConfig):
        return OpenAICompatibleProvider(profile, api_key=api_key)
    if isinstance(profile, AnthropicProviderConfig):
        if api_key is None:
            raise ConfigurationError(
                f"Environment variable {profile.api_key_env} is required for Anthropic"
            )
        return AnthropicProvider(profile, api_key=api_key)
```

OpenAI-compatible 本地服务允许不配置 API Key。Anthropic 必须解析到密钥。Transformers 在 Milestone 2 会明确返回“Milestone 10 才实现”的配置错误，而不是静默选择另一种模型。

## 12. 单轮 CLI

单轮执行函数只创建一个 user message：

```python
def run_once(provider: ModelProvider, prompt: str, *, stream: bool = False) -> str:
    if not prompt.strip():
        raise typer.BadParameter("prompt must not be empty")
    request = ModelRequest(
        messages=(Message(role=MessageRole.USER, content=prompt),),
    )
    tool_calls = ()
    if stream and provider.capabilities.supports_streaming:
        parts: list[str] = []
        for chunk in provider.stream(request):
            if chunk.text_delta:
                parts.append(chunk.text_delta)
                typer.echo(chunk.text_delta, nl=False)
            if chunk.tool_calls:
                tool_calls = chunk.tool_calls
        text = "".join(parts)
    else:
        response = provider.complete(request)
        text = response.content or ""
        if text:
            typer.echo(text)
        tool_calls = response.tool_calls
```

如果模型返回工具调用，CLI 只提示调用名称，不执行工具。工具执行需要 Milestone 4 的 MCP 层和 Milestone 5 的 Agent Loop。

CLI 注册命令并处理统一错误：

```python
@app.command("run")
def run_command(
    prompt: Annotated[str, typer.Argument(help="Prompt to send to the model.")],
    provider_name: Annotated[
        str | None,
        typer.Option("--provider", help="Provider profile to use."),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option("--stream/--no-stream", help="Stream text when supported."),
    ] = True,
) -> None:
    provider: ModelProvider | None = None
    try:
        config = load_config_from_search(Path.cwd())
        provider = create_provider(config, provider_name=provider_name)
        run_once(provider, prompt, stream=stream)
    except LeogentError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from None
    finally:
        if provider is not None:
            provider.close()
```

`finally` 保证成功和失败都释放 Provider 自己创建的 HTTP client。

## 13. 运行方式

在项目根目录创建 `.leogent/config.json`：

```json
{
  "default_provider": "local",
  "providers": {
    "local": {
      "type": "openai-compatible",
      "base_url": "http://localhost:11434/v1",
      "model": "qwen2.5-coder:7b",
      "context_window": 32768
    }
  }
}
```

然后运行：

```bash
leogent run "Explain what an agent loop is" --no-tui
leogent run "Explain what an agent loop is" --no-tui --no-stream
leogent run "hello" --provider local --no-tui
```

运行全部离线测试：

```bash
.venv/bin/pytest -q
```

真实 Provider 测试默认跳过。准备好配置和环境变量后，可以手动执行：

```bash
.venv/bin/pytest -m live tests/integration/test_live_provider.py -v
```

## 14. 本阶段边界

Milestone 2 完成了模型通信，但还没有：

- 保存模型调用到 Session。
- 执行模型返回的工具调用。
- 让模型根据工具结果继续循环。
- 自动压缩上下文。
- 在 TUI 中显示运行状态。

下一阶段的 Session 会记录这些模型请求与响应，使一次模型调用能够被恢复、查询和回放。
