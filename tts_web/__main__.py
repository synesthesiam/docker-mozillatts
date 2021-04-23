#!/usr/bin/env python3
"""Web server for synthesis"""
import argparse
import asyncio
import hashlib
import io
import logging
import signal
import sys
import time
import typing
import uuid
import wave
from pathlib import Path
from urllib.parse import parse_qs

import hypercorn
import quart_cors
from quart import Quart, Response, render_template, request, send_from_directory

import TTS

from .synthesize import Synthesizer

sys.modules["mozilla_voice_tts"] = TTS

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("mozillatts")
_LOOP = asyncio.get_event_loop()

# -----------------------------------------------------------------------------


def get_app(
    synthesizer: Synthesizer, cache_dir: typing.Optional[typing.Union[str, Path]] = None
):
    """Create Quart app and endpoints"""
    sample_rate = synthesizer.sample_rate

    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    def text_to_wav(text: str, lines_are_sentences: bool = True) -> bytes:
        _LOGGER.debug("Text: %s", text)

        wav_bytes: typing.Optional[bytes] = None
        cached_wav_path: typing.Optional[Path] = None

        if cache_dir:
            # Check cache first
            sentence_hash = hashlib.md5()
            sentence_hash.update(text.encode())
            cached_wav_path = cache_dir / f"{sentence_hash.hexdigest()}.wav"

            if cached_wav_path.is_file():
                _LOGGER.debug("Loading WAV from cache: %s", cached_wav_path)
                wav_bytes = cached_wav_path.read_bytes()

        if not wav_bytes:
            _LOGGER.info("Synthesizing (%s char(s))...", len(text))
            start_time = time.time()

            if lines_are_sentences:
                # Each line will be synthesized separately
                lines = text.strip().splitlines()
            else:
                # Entire text will be synthesized as one utterance
                lines = [text]

            # Synthesize each line separately.
            # Accumulate into a single WAV file.
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setframerate(sample_rate)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)

                    for line_index, line in enumerate(lines):
                        line = line.strip()
                        if not line:
                            # Skip blank lines
                            continue

                        _LOGGER.debug(
                            "Synthesizing line %s (%s char(s))",
                            line_index + 1,
                            len(line),
                        )
                        line_wav_bytes = synthesizer.synthesize(line)
                        _LOGGER.debug(
                            "Got %s WAV byte(s) for line %s",
                            len(line_wav_bytes),
                            line_index + 1,
                        )

                        # Open up and add to main WAV
                        with io.BytesIO(line_wav_bytes) as line_wav_io:
                            with wave.open(line_wav_io) as line_wav_file:
                                wav_file.writeframes(
                                    line_wav_file.readframes(line_wav_file.getnframes())
                                )

                wav_bytes = wav_io.getvalue()

            end_time = time.time()

            _LOGGER.debug(
                "Synthesized %s byte(s) in %s second(s)",
                len(wav_bytes),
                end_time - start_time,
            )

            # Save to cache
            if cached_wav_path:
                cached_wav_path.write_bytes(wav_bytes)

        return wav_bytes

    # -------------------------------------------------------------------------

    app = Quart("mozillatts", template_folder=str(_DIR / "templates"))
    app.secret_key = str(uuid.uuid4())
    app = quart_cors.cors(app)

    @app.route("/")
    async def app_index():
        return await render_template(
            "index.html",
            config=synthesizer.config,
            vocoder_config=synthesizer.vocoder_config,
        )

    css_dir = _DIR / "css"

    @app.route("/css/<path:filename>", methods=["GET"])
    async def css(filename) -> Response:
        """CSS static endpoint."""
        return await send_from_directory(css_dir, filename)

    img_dir = _DIR / "img"

    @app.route("/img/<path:filename>", methods=["GET"])
    async def img(filename) -> Response:
        """Image static endpoint."""
        return await send_from_directory(img_dir, filename)

    @app.route("/api/tts", methods=["GET", "POST"])
    def api_tts():
        """Text to speech endpoint"""
        if request.method == "POST":
            text = request.data.decode()
        else:
            text = request.args.get("text")

        lines_are_sentences = (
            request.args.get("linesAreSentences", "true").strip().lower() == "true"
        )

        wav_bytes = text_to_wav(text, lines_are_sentences=lines_are_sentences)

        return Response(wav_bytes, mimetype="audio/wav")

    # MaryTTS compatibility layer
    @app.route("/process", methods=["GET", "POST"])
    def api_process():
        """MaryTTS-compatible /process endpoint"""
        if request.method == "POST":
            data = parse_qs(request.get_data(as_text=True))
            text = data.get("INPUT_TEXT", [""])[0]
        else:
            text = request.args.get("INPUT_TEXT", "")

        wav_bytes = text_to_wav(text)

        return Response(wav_bytes, mimetype="audio/wav")

    @app.route("/voices", methods=["GET"])
    def api_voices():
        """MaryTTS-compatible /voices endpoint"""
        return "default\n"

    return app


# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for web server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=5002, help="Port for web server (default: 5002)"
    )
    parser.add_argument(
        "--model",
        help="Path to TTS model checkpoint (default: first .pth.tar in /app/model)",
    )
    parser.add_argument(
        "--config",
        help="Path to TTS model JSON config file (default: config.json next to checkpoint)",
    )
    parser.add_argument(
        "--vocoder-model",
        help="Path to vocoder model checkpoint (default: first .pth.tar in /app/model/vocoder)",
    )
    parser.add_argument(
        "--vocoder-config",
        help="Path to vocoder model JSON config file (default: config.json next to checkpoint)",
    )
    parser.add_argument(
        "--use-cuda", action="store_true", help="Use GPU (CUDA) for synthesis"
    )
    parser.add_argument(
        "--cache-dir", help="Path to directory to cache WAV files (default: no cache)"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Show DEBUG messages in the console"
    )

    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Fix logging (something in MozillaTTS is changing the level)
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    _LOGGER.debug(args)

    # Determine TTS checkpoint/config paths
    if not args.model:
        model_dir = Path("/app/model")
        _LOGGER.debug("Looking for TTS model checkpoint in %s", model_dir)
        for checkpoint_path in model_dir.glob("*.pth.tar"):
            args.model = checkpoint_path
            break
    else:
        args.model = Path(args.model)
        model_dir = args.model.parent

    assert (
        args.model and args.model.is_file()
    ), f"No TTS model checkpoint ({args.model})"

    if not args.config:
        args.config = model_dir / "config.json"
    else:
        args.config = Path(args.config)

    assert args.config and args.config.is_file(), f"No TTS config file ({args.config})"

    # Determine vocoder checkpoint/config paths
    if not args.vocoder_model:
        vocoder_dir = Path("/app/model/vocoder")
        if vocoder_dir.is_dir():
            _LOGGER.debug("Looking for vocoder model checkpoint in %s", vocoder_dir)
            for checkpoint_path in vocoder_dir.glob("*.pth.tar"):
                args.vocoder_model = checkpoint_path
                break
    else:
        args.vocoder_model = Path(args.vocoder_model)
        vocoder_dir = args.vocoder_model.parent

    if args.vocoder_model:
        assert (
            args.vocoder_model.is_file()
        ), f"No vocoder model checkpoint ({args.vocoder_model})"

        if not args.vocoder_config:
            args.vocoder_config = vocoder_dir / "config.json"
        else:
            args.vocoder_config = Path(args.vocoder_config)

        assert (
            args.vocoder_config and args.vocoder_config.is_file()
        ), f"No vocoder config file ({args.vocoder_config})"

    # Create synthesizer
    _LOGGER.debug("Creating synthesizer...")
    synthesizer = Synthesizer(
        config_path=args.config,
        model_path=args.model,
        use_cuda=args.use_cuda,
        vocoder_path=args.vocoder_model,
        vocoder_config_path=args.vocoder_config,
    )

    synthesizer.load()

    # Create Quart web app
    app = get_app(synthesizer, cache_dir=args.cache_dir)

    # -------------------------------------------------------------------------

    # Run Hypercorn web server
    hyp_config = hypercorn.config.Config()
    hyp_config.bind = [f"{args.host}:{args.port}"]

    # Create shutdown event for Hypercorn
    shutdown_event = asyncio.Event()

    def _signal_handler(*_: typing.Any) -> None:
        """Signal shutdown to Hypercorn"""
        shutdown_event.set()

    _LOOP.add_signal_handler(signal.SIGTERM, _signal_handler)

    try:
        # Need to type cast to satisfy mypy
        shutdown_trigger = typing.cast(
            typing.Callable[..., typing.Awaitable[None]], shutdown_event.wait
        )

        _LOOP.run_until_complete(
            hypercorn.asyncio.serve(app, hyp_config, shutdown_trigger=shutdown_trigger)
        )
    except KeyboardInterrupt:
        _LOOP.call_soon(shutdown_event.set)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
