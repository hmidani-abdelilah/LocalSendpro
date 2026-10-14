
from playsound3 import playsound

# Play a local WAV file synchronously (blocks execution until finished)
playsound("./assets/notification.wav")

# Play a WAV file asynchronously (runs in a background thread)
playsound("./assets/notification.wav", block=False)
