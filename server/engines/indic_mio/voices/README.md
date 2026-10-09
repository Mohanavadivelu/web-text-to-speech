# Indic-Mio voice embeddings

Each `<voice id>.npy` is a 128-number speaker embedding for MioCodec-25Hz-24kHz. The
language model decides *what* is said; this embedding decides *who* says it, so every
voice works in every language.

Made by `scripts/make_indic_voices.py` from these recordings:

| Voice | Source recording | Licence |
|---|---|---|
| Ananya (female, native) | `samples/sample1.wav` on [SPRINGLab/Indic-Mio](https://huggingface.co/SPRINGLab/Indic-Mio) (Hinglish) | Apache-2.0 |
| Vikram (male, native) | `samples/sample2.wav` (English) | Apache-2.0 |
| Arjun (male, native) | `samples/sample3.wav` (Gujarati) | Apache-2.0 |
| Karthik (male, native) | `samples/sample4.wav` (Tamil) | Apache-2.0 |
| Heart, Bella, Emma, Michael, Fenrir, George | Kokoro-82M (`af_heart`, `af_bella`, `bf_emma`, `am_michael`, `am_fenrir`, `bm_george`) reading a fixed passage | Apache-2.0 |

The native samples are themselves outputs of Indic-Mio; the voice names are ours.
Measured median pitch is preserved within a few hertz when a voice speaks Hindi or
Tamil (female 185–260 Hz, male 100–145 Hz).
