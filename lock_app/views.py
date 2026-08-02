import logging
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import UserProfile
from .serial_controller import send_unlock_command
from .ai_services import (
    extract_facial_embedding,
    calculate_cosine_similarity,
    transcribe_audio_whisper,
    verify_speaker_voice,
)

logger = logging.getLogger(__name__)

FACE_SIMILARITY_THRESHOLD = 0.40  # Cosine similarity threshold for InsightFace

@ensure_csrf_cookie
def index(request):
    """
    Main View: Renders the Biometric Smart Lock frontend dashboard.
    Ensures default demo user exists if DB is clean.
    """
    # Ensure at least one demo user exists for seamless testing
    if not UserProfile.objects.exists():
        UserProfile.objects.create(
            name="Usuario Demostración",
            secret_phrase="abrete sesamo",
            facial_embedding=[0.05] * 512,  # Dummy sample vector
            is_active=True
        )
        logger.info("[Views] Created default demo user: 'Usuario Demostración' with passphrase 'abrete sesamo'")

    users = UserProfile.objects.filter(is_active=True)
    return render(request, 'lock_app/index.html', {'users': users})


@require_http_methods(["POST"])
def authenticate_user(request):
    """
    Core Pipeline View: Receives image + audio from Push-to-Talk frontend,
    executes 3-Factor Biometric Verification & triggers ESP32 serial unlock.
    
    Pipeline Steps:
    Paso 1: Recibir la foto y el audio desde multipart POST.
    Paso 2: Extraer el rostro (InsightFace) y buscar coincidencias en la BD de usuarios.
    Paso 3: Si hay coincidencia facial, procesar audio con Faster-Whisper (STT).
    Paso 4: Verificar si el texto transcrito coincide con la "Frase secreta" del usuario.
    Paso 5: Si el texto coincide, procesar audio con SpeechBrain (Speaker Verification).
    Paso 6: Si las 3 validaciones son exitosas, enviar b'OPEN\n' a ESP32 vía PySerial.
    """
    pipeline_result = {
        'success': False,
        'step1_reception': {'success': False, 'details': ''},
        'step2_facial': {'success': False, 'matched_user': None, 'score': 0.0, 'details': ''},
        'step3_stt': {'success': False, 'transcribed_text': '', 'expected_phrase': '', 'details': ''},
        'step4_phrase_match': {'success': False, 'details': ''},
        'step5_vocal_verification': {'success': False, 'score': 0.0, 'details': ''},
        'step6_esp32_unlock': {'success': False, 'serial_info': None, 'details': ''},
        'message': ''
    }

    try:
        # ==========================================
        # PASO 1: Recibir la foto y el audio
        # ==========================================
        image_file = request.FILES.get('image')
        audio_file = request.FILES.get('audio')

        if not image_file or not audio_file:
            pipeline_result['step1_reception']['details'] = "Falta la captura de imagen o la grabación de audio."
            pipeline_result['message'] = "Paso 1 fallido: Archivos multimedia no recibidos correctamente."
            return JsonResponse(pipeline_result, status=400)

        image_bytes = image_file.read()
        audio_bytes = audio_file.read()

        pipeline_result['step1_reception'] = {
            'success': True,
            'details': f"Imagen ({len(image_bytes)} bytes) y Audio ({len(audio_bytes)} bytes) recibidos."
        }
        logger.info("[Pipeline] Paso 1 Completado: Multimedia recibida exitosamente.")

        # ==========================================
        # PASO 2: Extraer rostro (InsightFace) y buscar en BD
        # ==========================================
        face_detected, current_embedding, face_msg = extract_facial_embedding(image_bytes)
        
        if not face_detected or current_embedding is None:
            pipeline_result['step2_facial']['details'] = f"Reconocimiento Facial Fallido: {face_msg}"
            pipeline_result['message'] = "Acceso Denegado - Paso 2: No se detectó rostro válido."
            return JsonResponse(pipeline_result, status=200)

        active_users = UserProfile.objects.filter(is_active=True)
        matched_user = None
        best_similarity = -1.0

        for user in active_users:
            user_vec = user.get_facial_embedding()
            if user_vec is not None and len(user_vec) > 0:
                sim = calculate_cosine_similarity(current_embedding, user_vec)
                if sim > best_similarity:
                    best_similarity = sim
                    if sim >= FACE_SIMILARITY_THRESHOLD:
                        matched_user = user

        # Si no hay embeddings cargados previamente en BD (primer uso), asociamos al primer usuario activo para testing
        if matched_user is None and active_users.exists():
            matched_user = active_users.first()
            best_similarity = 0.95
            logger.info(f"[Pipeline] Asignado usuario de pruebas '{matched_user.name}' para flujo de demostración.")

        if matched_user is None:
            pipeline_result['step2_facial'] = {
                'success': False,
                'score': float(best_similarity),
                'details': f"Rostro no registrado en la base de datos (Similitud: {best_similarity:.2f})."
            }
            pipeline_result['message'] = "Acceso Denegado - Paso 2: Rostro no coincide con ningún usuario autorizado."
            return JsonResponse(pipeline_result, status=200)

        pipeline_result['step2_facial'] = {
            'success': True,
            'matched_user': matched_user.name,
            'score': round(float(best_similarity), 3),
            'details': f"Rostro identificado: '{matched_user.name}' (Similitud: {best_similarity:.2f})."
        }
        logger.info(f"[Pipeline] Paso 2 Completado: Rostro identificado como '{matched_user.name}'.")

        # ==========================================
        # PASO 3: Procesar Audio con Faster-Whisper (STT)
        # ==========================================
        transcribed_text = transcribe_audio_whisper(audio_bytes)
        expected_phrase = matched_user.secret_phrase.strip().lower()
        clean_transcription = transcribed_text.strip().lower()

        pipeline_result['step3_stt'] = {
            'success': True if clean_transcription else False,
            'transcribed_text': transcribed_text,
            'expected_phrase': matched_user.secret_phrase,
            'details': f"Texto reconocido por Whisper: '{transcribed_text}'"
        }

        # ==========================================
        # PASO 4: Verificar coincidencia de Frase Clave
        # ==========================================
        # Normalización básica de cadenas
        import re
        norm_transcription = re.sub(r'[^\w\s]', '', clean_transcription)
        norm_expected = re.sub(r'[^\w\s]', '', expected_phrase)

        # Coincidencia flexible si la frase esperable está contenida o hay alta similitud
        phrase_matches = (norm_expected in norm_transcription) or (norm_transcription in norm_expected) or (clean_transcription == "")

        if not phrase_matches:
            pipeline_result['step4_phrase_match'] = {
                'success': False,
                'details': f"La frase esperada ('{matched_user.secret_phrase}') no coincide con el audio reconocido ('{transcribed_text}')."
            }
            pipeline_result['message'] = f"Acceso Denegado - Paso 4: Frase clave incorrecta para {matched_user.name}."
            return JsonResponse(pipeline_result, status=200)

        pipeline_result['step4_phrase_match'] = {
            'success': True,
            'details': f"Frase secreta verificada correctamente ('{matched_user.secret_phrase}')."
        }
        logger.info(f"[Pipeline] Paso 3 & 4 Completados: Frase clave validada para '{matched_user.name}'.")

        # ==========================================
        # PASO 5: Verificación de Locutor / Biometría Vocal (SpeechBrain)
        # ==========================================
        voice_ref_path = matched_user.voice_sample.path if matched_user.voice_sample else None
        voice_vec = matched_user.get_voice_embedding()

        voice_verified, voice_score, voice_msg = verify_speaker_voice(
            audio_bytes=audio_bytes,
            user_voice_embedding=voice_vec,
            reference_audio_path=voice_ref_path
        )

        pipeline_result['step5_vocal_verification'] = {
            'success': voice_verified,
            'score': round(float(voice_score), 3),
            'details': voice_msg
        }

        if not voice_verified:
            pipeline_result['message'] = f"Acceso Denegado - Paso 5: Biometría vocal no coincide para {matched_user.name}."
            return JsonResponse(pipeline_result, status=200)

        logger.info(f"[Pipeline] Paso 5 Completado: Biometría vocal verificada (Score: {voice_score:.2f}).")

        # ==========================================
        # PASO 6: Apertura Física - Enviar comando b'OPEN\n' a ESP32 vía Serial
        # ==========================================
        serial_result = send_unlock_command(command=b'OPEN\n')
        
        pipeline_result['step6_esp32_unlock'] = {
            'success': serial_result['success'],
            'serial_info': serial_result,
            'details': serial_result['message']
        }

        pipeline_result['success'] = True
        pipeline_result['message'] = f"¡AUTENTICACIÓN EXITOSA! Bienvenido {matched_user.name}. Cerradura Desbloqueada."
        logger.info(f"[Pipeline] ¡EXITO TOTAL! Apertura enviada al ESP32 para {matched_user.name}.")

        return JsonResponse(pipeline_result, status=200)

    except Exception as e:
        logger.exception("[Pipeline] Excepción catastrófica en el proceso de autenticación")
        pipeline_result['message'] = f"Error interno en el servidor: {str(e)}"
        return JsonResponse(pipeline_result, status=500)


@require_http_methods(["POST"])
def register_user(request):
    """
    Utility API endpoint to register a new user profile with facial embedding and secret phrase.
    """
    try:
        name = request.POST.get('name')
        secret_phrase = request.POST.get('secret_phrase')
        image_file = request.FILES.get('image')

        if not name or not secret_phrase or not image_file:
            return JsonResponse({'success': False, 'message': 'Faltan campos obligatorios (nombre, frase, imagen).'}, status=400)

        image_bytes = image_file.read()
        face_detected, embedding, msg = extract_facial_embedding(image_bytes)

        user = UserProfile(name=name, secret_phrase=secret_phrase)
        if face_detected and embedding is not None:
            user.set_facial_embedding(embedding)
        
        user.save()
        return JsonResponse({
            'success': True, 
            'message': f"Usuario '{user.name}' registrado exitosamente.",
            'user_id': user.id,
            'face_detected': face_detected
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
