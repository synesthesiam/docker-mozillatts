#!/usr/bin/env python3
"""Web server for synthesis"""
import argparse
import hashlib
import io
import logging
import sys
import time
import typing
import uuid
import wave
from pathlib import Path

import TTS
from flask import Flask, Response, render_template, request, send_from_directory
from flask_cors import CORS

from .synthesize import Synthesizer

sys.modules["mozilla_voice_tts"] = TTS

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("mozillatts")

# -----------------------------------------------------------------------------


def get_app(
    synthesizer: Synthesizer, cache_dir: typing.Optional[typing.Union[str, Path]] = None
):
    """Create Flask app and endpoints"""
    sample_rate = synthesizer.sample_rate

    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

    def text_to_wav(text: str) -> bytes:
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

            # Synthesize each line separately.
            # Accumulate into a single WAV file.
            with io.BytesIO() as wav_io:
                with wave.open(wav_io, "wb") as wav_file:
                    wav_file.setframerate(sample_rate)
                    wav_file.setsampwidth(2)
                    wav_file.setnchannels(1)

                    for line_index, line in enumerate(text.strip().splitlines()):
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

    app = Flask("mozillatts", template_folder=str(_DIR / "templates"))
    app.secret_key = str(uuid.uuid4())
    CORS(app)

    @app.route("/")
    def app_index():
        return render_template(
            "index.html",
            config=synthesizer.config,
            vocoder_config=synthesizer.vocoder_config,
        )

    css_dir = _DIR / "css"

    @app.route("/css/<path:filename>", methods=["GET"])
    def css(filename) -> Response:
        """CSS static endpoint."""
        return send_from_directory(css_dir, filename)

    img_dir = _DIR / "img"

    @app.route("/img/<path:filename>", methods=["GET"])
    def img(filename) -> Response:
        """Image static endpoint."""
        return send_from_directory(img_dir, filename)

    @app.route("/api/tts", methods=["GET", "POST"])
    def api_tts():
        """Text to speech endpoint"""
        if request.method == "POST":
            text = request.data.decode()
        else:
            text = request.args.get("text")

        wav_bytes = text_to_wav(text)

        return Response(wav_bytes, mimetype="audio/wav")

    # MaryTTS compatibility layer
    @app.route("/process", methods=["GET", "POST"])
    def api_process():
        """MaryTTS-compatible /process endpoint"""
        if request.method == "POST":
            text = request.get_data(as_text=True)
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

    # Create Flask web app
    app = get_app(synthesizer, cache_dir=args.cache_dir)
    app.run(host=args.host, port=args.port)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
