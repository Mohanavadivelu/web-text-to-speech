"""Languages and voices of the Indic-Mio engine.

Indic-Mio reads text in all 22 scheduled Indian languages and English. A voice is a
128-number "global embedding" for the audio codec: the language model decides what
is said, the embedding decides who says it, so every voice speaks every language.

Voice embeddings (voices/<id>.npy) are made by scripts/make_indic_voices.py from:
  - the four sample recordings on the Indic-Mio model card (Apache-2.0), and
  - Kokoro-82M recordings of its own voices (Apache-2.0), so "Heart" sounds the same
    in English (Kokoro) and in Tamil (Indic-Mio).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from server.engines import base

ENGINE = "indic_mio"
EMBEDDINGS_DIR = Path(__file__).resolve().parent / "voices"

INDIC_EMOTIONS = ("happy", "sad", "angry", "disgust", "fear", "surprise")
ENGLISH_EMOTIONS = ("happy", "sad", "enunciated", "confused", "angry", "whisper")

# The first voice is the default. "native": recorded by an Indian speaker.
VOICES: tuple[base.Voice, ...] = (
    base.Voice("in_ananya", "Ananya", "female", tags=("native",)),
    base.Voice("in_vikram", "Vikram", "male", tags=("native",)),
    base.Voice("in_arjun", "Arjun", "male", tags=("native",)),
    base.Voice("in_karthik", "Karthik", "male", tags=("native",)),
    base.Voice("in_heart", "Heart", "female"),
    base.Voice("in_bella", "Bella", "female"),
    base.Voice("in_emma", "Emma", "female"),
    base.Voice("in_michael", "Michael", "male"),
    base.Voice("in_fenrir", "Fenrir", "male"),
    base.Voice("in_george", "George", "male"),
)
VOICE_IDS = frozenset(v.id for v in VOICES)

# (code, name, preview text). Codes are ISO 639; Indian English is "en-in" so it never
# clashes with Kokoro's English. Preview texts marked * still need a native review.
_LANGUAGES: tuple[tuple[str, str, str], ...] = (
    ("hi", "Hindi", "नमस्ते! मेरी आवाज़ ऐसी सुनाई देती है।"),
    ("bn", "Bengali", "নমস্কার! আমার কণ্ঠস্বর এরকম শোনায়।"),
    ("mr", "Marathi", "नमस्कार! माझा आवाज असा ऐकू येतो."),
    ("te", "Telugu", "నమస్కారం! నా గొంతు ఇలా వినిపిస్తుంది."),
    ("ta", "Tamil", "வணக்கம்! என் குரல் இப்படித்தான் ஒலிக்கும்."),
    ("gu", "Gujarati", "નમસ્તે! મારો અવાજ આવો સંભળાય છે."),
    ("kn", "Kannada", "ನಮಸ್ಕಾರ! ನನ್ನ ಧ್ವನಿ ಹೀಗೆ ಕೇಳಿಸುತ್ತದೆ."),
    ("ml", "Malayalam", "നമസ്കാരം! എന്റെ ശബ്ദം ഇങ്ങനെയാണ്."),
    ("pa", "Punjabi", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੇਰੀ ਆਵਾਜ਼ ਇਸ ਤਰ੍ਹਾਂ ਸੁਣਾਈ ਦਿੰਦੀ ਹੈ।"),
    ("or", "Odia", "ନମସ୍କାର! ମୋ ସ୍ୱର ଏମିତି ଶୁଣାଯାଏ।"),
    ("as", "Assamese", "নমস্কাৰ! মোৰ মাতটো এনেকুৱা শুনা যায়।"),
    ("ur", "Urdu", "السلام علیکم! میری آواز ایسی سنائی دیتی ہے۔"),
    ("ne", "Nepali", "नमस्ते! मेरो आवाज यस्तो सुनिन्छ।"),
    ("sa", "Sanskrit", "नमः! मम स्वरः एवं श्रूयते।"),
    ("mai", "Maithili", "प्रणाम! हमर आवाज एहन सुनाइ दैत अछि।"),  # *
    ("kok", "Konkani", "नमस्कार! म्हजो आवाज असो आयकूंक येता."),  # *
    ("doi", "Dogri", "नमस्ते! मेरी आवाज़ इʼयां सुनचदी ऐ।"),  # *
    ("brx", "Bodo", "नमस्कार! आंनि गाबखांआ बेबादि खोनानो मोनो।"),  # *
    ("sd", "Sindhi", "سلام! منهنجو آواز هن طرح ٻڌڻ ۾ اچي ٿو."),  # *
    ("ks", "Kashmiri", "السلام علیکم! میون آواز چھُ یِتھ پاٹھۍ بوزنہٕ یِوان۔"),  # *
    ("mni", "Manipuri", "খুরুমজরি! ঐগী খোনজেল অসিগুম্বা তাই।"),  # *
    ("sat", "Santali", "ᱡᱚᱦᱟᱨ! ᱤᱧᱟᱜ ᱟᱲᱟᱝ ᱱᱚᱶᱟ ᱞᱮᱠᱟ ᱟᱭᱩᱨ ᱠᱟᱱᱟ᱾"),  # *
    ("en-in", "English (India)", "Hello! This is how my voice sounds."),
)


def catalog() -> list[base.Language]:
    return [
        base.Language(
            code=code,
            name=name,
            engine=ENGINE,
            preview_text=preview,
            voices=VOICES,
            emotions=ENGLISH_EMOTIONS if code == "en-in" else INDIC_EMOTIONS,
        )
        for code, name, preview in _LANGUAGES
    ]


LANGUAGE_CODES = frozenset(code for code, _, _ in _LANGUAGES)


def validate(lang: str, voice_id: str, blend_voice: str | None = None) -> None:
    if lang not in LANGUAGE_CODES:
        raise ValueError(f"Unknown language '{lang}'.")
    for vid in filter(None, (voice_id, blend_voice)):
        if vid not in VOICE_IDS:
            raise ValueError(f"Unknown voice '{vid}'.")


@lru_cache(maxsize=32)
def load_embedding(voice_id: str) -> np.ndarray:
    if voice_id not in VOICE_IDS:
        raise ValueError(f"Unknown voice '{voice_id}'.")
    embedding = np.load(EMBEDDINGS_DIR / f"{voice_id}.npy").astype(np.float32).reshape(-1)
    embedding.flags.writeable = False
    return embedding


def voice_embedding(
    voice_id: str, blend_voice: str | None = None, blend_ratio: float = 0.5
) -> np.ndarray:
    """The voice's embedding, optionally mixed with a second voice (blend_ratio = its share)."""
    base_embedding = load_embedding(voice_id)
    if not blend_voice or blend_voice == voice_id or blend_ratio <= 0:
        return base_embedding
    ratio = min(1.0, float(blend_ratio))
    mixed = (1.0 - ratio) * base_embedding + ratio * load_embedding(blend_voice)
    return mixed.astype(np.float32)
