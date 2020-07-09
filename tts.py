#!/usr/bin/env python3
import io
import os
import time
from pathlib import Path

import torch
from flask import Flask, Response, render_template, request
from flask_cors import CORS
from TTS.utils.generic_utils import setup_model
from TTS.utils.io import load_config
from TTS.utils.text.symbols import symbols, phonemes
from TTS.utils.audio import AudioProcessor
from TTS.utils.synthesis import synthesis
from TTS.vocoder.utils.generic_utils import setup_generator

_DIR = Path(__file__).parent

# -----------------------------------------------------------------------------


def tts(model, text, CONFIG, use_cuda: bool, ap, use_gl: bool):
    waveform, alignment, mel_spec, mel_postnet_spec, stop_tokens, inputs = synthesis(
        model,
        text,
        CONFIG,
        use_cuda,
        ap,
        speaker_id,
        style_wav=None,
        truncated=False,
        enable_eos_bos_chars=CONFIG.enable_eos_bos_chars,
    )
    # mel_postnet_spec = ap._denormalize(mel_postnet_spec.T)
    if not use_gl:
        waveform = vocoder_model.inference(
            torch.FloatTensor(mel_postnet_spec.T).unsqueeze(0)
        )
        waveform = waveform.flatten()
    if use_cuda:
        waveform = waveform.cpu()

    waveform = waveform.numpy()

    return alignment, mel_postnet_spec, stop_tokens, waveform


# -----------------------------------------------------------------------------

# runtime settings
use_cuda = False

# model paths
TTS_MODEL = _DIR / "model" / "checkpoint_130000.pth.tar"
TTS_CONFIG = _DIR / "model" / "config.json"
VOCODER_MODEL = _DIR / "vocoder" / "checkpoint_1450000.pth.tar"
VOCODER_CONFIG = _DIR / "vocoder" / "config.json"

# load configs
TTS_CONFIG = load_config(TTS_CONFIG)
VOCODER_CONFIG = load_config(VOCODER_CONFIG)

# load the audio processor
ap = AudioProcessor(**TTS_CONFIG.audio)

# LOAD TTS MODEL
# multi speaker
speaker_id = None
speakers = []

# load the model
num_chars = len(phonemes) if TTS_CONFIG.use_phonemes else len(symbols)
model = setup_model(num_chars, len(speakers), TTS_CONFIG)

# load model state
cp = torch.load(TTS_MODEL, map_location=torch.device("cpu"))

# load the model
model.load_state_dict(cp["model"])
if use_cuda:
    model.cuda()

model.eval()

# set model stepsize
if "r" in cp:
    model.decoder.set_r(cp["r"])

# LOAD VOCODER MODEL
vocoder_model = setup_generator(VOCODER_CONFIG)
vocoder_model.load_state_dict(torch.load(VOCODER_MODEL, map_location="cpu")["model"])
vocoder_model.remove_weight_norm()
vocoder_model.inference_padding = 0

ap_vocoder = AudioProcessor(**VOCODER_CONFIG["audio"])
if use_cuda:
    vocoder_model.cuda()

vocoder_model.eval()

# -----------------------------------------------------------------------------

app = Flask("mozillatts")
CORS(app)

# -----------------------------------------------------------------------------


@app.route("/api/tts")
def api_tts():
    text = request.args.get("text", "").strip()
    align, spec, stop_tokens, wav = tts(
        model, text, TTS_CONFIG, use_cuda, ap, use_gl=False
    )

    with io.BytesIO() as out:
        ap.save_wav(wav, out)
        return Response(out.getvalue(), mimetype="audio/wav")


@app.route("/")
def index():
    return render_template("index.html")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
