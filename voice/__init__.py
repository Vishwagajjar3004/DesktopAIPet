"""
voice package
-------------
Speech-to-text, text-to-speech, and wake-word listening.

All three modules are designed to *degrade gracefully*: if an optional
dependency (pyttsx3 / SpeechRecognition / a microphone) isn't available
on the current machine, the relevant class logs a warning and becomes a
harmless no-op instead of crashing the whole application. This matters
because Asha must still run fine on a headless dev box or a machine
with no microphone.
"""
