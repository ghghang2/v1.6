import logging
import time
from openai import OpenAI
from .config import SERVER_URL

_handler = logging.FileHandler("inference_metrics.log")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger = logging.getLogger("Inference_Metrics")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False  # don't bubble up to root logger / console


class _InterceptedStream:
    """Proxies an OpenAI Stream, intercepting iteration to log metrics."""

    def __init__(self, stream, start_time):
        self._stream = stream
        self._start_time = start_time

    def __iter__(self):
        ttft = None
        usage = None
        try:
            for chunk in self._stream:
                if ttft is None and chunk.choices and chunk.choices[0].delta.content:
                    ttft = time.time() - self._start_time
                    logger.info("Metrics | TTFT: %.3fs", ttft)
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                if not chunk.choices:  # usage-only sentinel chunk — our instrumentation artefact, don't leak it
                    continue
                yield chunk
        except Exception as e:
            logger.error("Metrics | Stream error after %.2fs: %s", time.time() - self._start_time, e)
            raise
        finally:
            total = time.time() - self._start_time
            if usage:
                logger.info(
                    "Metrics | Stream latency: %.2fs | Prompt: %d | Completion: %d | Total: %d",
                    total, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                )
            else:
                logger.warning("Metrics | Stream latency: %.2fs | No usage data.", total)

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, *args):
        return self._stream.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _CompletionsWrapper:
    def __init__(self, completions):
        self._completions = completions

    def create(self, *args, **kwargs):
        if kwargs.get("stream"):
            kwargs.setdefault("stream_options", {})
            kwargs["stream_options"].setdefault("include_usage", True)

        start_time = time.time()
        try:
            response = self._completions.create(*args, **kwargs)
        except Exception as e:
            logger.error("Metrics | Request failed after %.2fs: %s", time.time() - start_time, e)
            raise

        if kwargs.get("stream"):
            return _InterceptedStream(response, start_time)

        latency = time.time() - start_time
        u = getattr(response, "usage", None)
        if u:
            logger.info(
                "Metrics | Latency: %.2fs | Prompt: %d | Completion: %d | Total: %d",
                latency, u.prompt_tokens, u.completion_tokens, u.total_tokens,
            )
        else:
            logger.warning("Metrics | Latency: %.2fs | No usage data.", latency)
        return response


class _ChatWrapper:
    def __init__(self, chat):
        self._chat = chat
        self.completions = _CompletionsWrapper(chat.completions)

    def __getattr__(self, name):
        return getattr(self._chat, name)


class MetricsLoggingClient:
    def __init__(self, client: OpenAI):
        self._client = client
        self.chat = _ChatWrapper(client.chat)

    def __getattr__(self, name):
        return getattr(self._client, name)


def get_client() -> MetricsLoggingClient:
    return MetricsLoggingClient(OpenAI(base_url=f"{SERVER_URL}/v1", api_key="sk-local"))