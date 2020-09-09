# Mozilla TTS

Docker image for [Mozilla TTS](https://github.com/mozilla/TTS).

Includes [@erogol's](https://github.com/erogol) pre-built LJSpeech Tacotron2 English model and Multiband MelGAN vocoder.
See [below](#building-yourself) for links to specific checkpoints.

## Using

```sh
$ docker run -it -p 5002:5002 synesthesiam/mozillatts
```

Visit http://localhost:5002 for web interface.

Do HTTP GET at http://localhost:5002/api/tts?text=your%20sentence to get WAV audio back:

```sh
$ curl -G --output - \
    --data-urlencode 'text=Welcome to the world of speech synthesis!' \
    'http://localhost:5002/api/tts' | \
    aplay
```

## Building Yourself

The Docker image is built using [these instructions](https://colab.research.google.com/drive/1u_16ZzHjKYFn1HNVuA4Qf_i2MMFB9olY?usp=sharing#scrollTo=FuWxZ9Ey5Puj). You'll need to manually download the model and vocoder checkpoints/configs:

* [`model/config.json`](https://drive.google.com/uc?id=18CQ6G6tBEOfvCHlPqP8EBI4xWbrr9dBc)
* [`model/checkpoint_130000.pth.tar`](https://drive.google.com/uc?id=1dntzjWFg7ufWaTaFy80nRz-Tu02xWZos)
* [`vocoder/config.json`](https://drive.google.com/uc?id=1Rd0R_nRCrbjEdpOwq6XwZAktvugiBvmu)
* [`vocoder/checkpoint_1450000.pth.tar`](https://drive.google.com/uc?id=1Ty5DZdOc0F7OTGj9oJThYbL5iVu_2G0K)


