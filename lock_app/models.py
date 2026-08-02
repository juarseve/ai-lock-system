from django.db import models
import json
import numpy as np

class UserProfile(models.Model):
    """
    Model representing an authorized user in the Biometric Smart Lock System.
    Stores biometric facial embeddings, voice fingerprint references, and secret passphrases.
    """
    name = models.CharField(max_length=150, help_text="Nombre completo del usuario registrado")
    secret_phrase = models.CharField(
        max_length=255, 
        help_text="Frase secreta requerida para la verificación STT (en texto plano)"
    )
    
    # Facial Embedding vector from InsightFace (128-d or 512-d float array stored as JSON)
    facial_embedding = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Vector numérico (embedding) facial de InsightFace"
    )
    
    # Speaker Verification Voice Embedding / audio feature reference
    voice_embedding = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Embedding o huella vocal de referencia de SpeechBrain (ECAPA-TDNN)"
    )
    
    voice_sample = models.FileField(
        upload_to='voice_samples/', 
        null=True, 
        blank=True, 
        help_text="Archivo de audio de referencia para verificación vocal"
    )
    
    is_active = models.BooleanField(default=True, help_text="Indica si el usuario tiene permiso de acceso")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_facial_embedding(self, np_vector):
        """Converts a numpy vector to a Python list for JSON storing."""
        if isinstance(np_vector, np.ndarray):
            self.facial_embedding = np_vector.tolist()
        else:
            self.facial_embedding = list(np_vector)

    def get_facial_embedding(self):
        """Returns the facial embedding as a numpy array."""
        if not self.facial_embedding:
            return None
        return np.array(self.facial_embedding, dtype=np.float32)

    def set_voice_embedding(self, np_vector):
        """Converts a numpy array/tensor to list for JSON storing."""
        if isinstance(np_vector, np.ndarray):
            self.voice_embedding = np_vector.tolist()
        else:
            self.voice_embedding = list(np_vector)

    def get_voice_embedding(self):
        """Returns the voice embedding as a numpy array."""
        if not self.voice_embedding:
            return None
        return np.array(self.voice_embedding, dtype=np.float32)

    def __str__(self):
        return f"{self.name} (Activo: {self.is_active})"
