"""
Marcelly — Voz local.
Transcreve comandos de voz no próprio computador (faster-whisper) e
responde em voz alta (pyttsx3). Nenhum áudio ou texto vai para a nuvem.
"""
import logging
import tempfile
import threading
from pathlib import Path

log = logging.getLogger("marcelly")


class VoiceEngine:
    """Reconhecimento e síntese de fala 100% locais."""

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self._tts_lock = threading.Lock()

    # ---------- Reconhecimento (STT) ----------
    def _get_model(self):
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                log.info("Carregando modelo de voz local (download pequeno, só na primeira vez)...")
                self._model = WhisperModel("base", device="cpu", compute_type="int8")
            return self._model

    def transcribe(self, audio_bytes: bytes, extension: str = "webm") -> str:
        model = self._get_model()
        with tempfile.NamedTemporaryFile(suffix="." + extension, delete=False) as tmp:
            tmp.write(audio_bytes)
            path = tmp.name
        try:
            segments, _info = model.transcribe(path, language="pt", vad_filter=True)
            return " ".join(s.text.strip() for s in segments).strip()
        finally:
            Path(path).unlink(missing_ok=True)

    # ---------- Síntese (TTS) ----------
    def speak(self, text: str) -> None:
        """Fala o texto em uma thread dedicada (não bloqueia o WebSocket)."""
        threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()

    def _speak_sync(self, text: str) -> None:
        try:
            import pyttsx3
            with self._tts_lock:
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                for v in engine.getProperty("voices"):
                    name = (v.name or "").lower()
                    ident = (v.id or "").lower()
                    if "luciana" in name or "brazil" in name or "pt-br" in ident:
                        engine.setProperty("voice", v.id)
                        break
                engine.say(text[:600])
                engine.runAndWait()
                engine.stop()
        except Exception as e:
            log.warning("Resposta em voz indisponível: %s", e)
