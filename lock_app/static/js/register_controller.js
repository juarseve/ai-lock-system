/**
 * User Biometric Registration Controller (Vanilla JS)
 * Captures face photo snapshot & records voice sample audio before submitting to Django.
 */

document.addEventListener('DOMContentLoaded', () => {
    const regWebcamVideo = document.getElementById('reg-webcam-feed');
    const regSnapshotCanvas = document.getElementById('reg-snapshot-canvas');
    const btnCaptureFace = document.getElementById('btn-capture-face');
    const faceStatus = document.getElementById('face-status');
    
    const btnRecordVoice = document.getElementById('btn-record-voice');
    const voiceStatus = document.getElementById('voice-status');
    const audioPreview = document.getElementById('audio-preview');

    const regForm = document.getElementById('register-form');
    const regResponseMsg = document.getElementById('reg-response-msg');

    let mediaStream = null;
    let capturedFaceBlob = null;
    let capturedVoiceBlob = null;
    let isRecordingVoice = false;

    // 1. Initialize Webcam & Mic
    async function initMedia() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Navegador no permite cámara/micrófono en conexiones HTTP no seguras. Acceda usando http://localhost:8000');
            return;
        }

        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: true
            });
            regWebcamVideo.srcObject = mediaStream;
        } catch (err) {
            console.warn('[RegController] Fallback basic constraints:', err);
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                regWebcamVideo.srcObject = mediaStream;
            } catch (e) {
                console.error('[RegController] Error opening camera/mic:', e);
                alert('No se pudo acceder a la cámara o al micrófono para el registro.');
            }
        }
    }

    initMedia();

    // 2. Capture Face Snapshot
    btnCaptureFace.addEventListener('click', () => {
        if (!regWebcamVideo.videoWidth) {
            alert('Cámara no lista aún.');
            return;
        }
        regSnapshotCanvas.width = regWebcamVideo.videoWidth;
        regSnapshotCanvas.height = regWebcamVideo.videoHeight;
        const ctx = regSnapshotCanvas.getContext('2d');
        ctx.drawImage(regWebcamVideo, 0, 0, regSnapshotCanvas.width, regSnapshotCanvas.height);

        regSnapshotCanvas.toBlob((blob) => {
            capturedFaceBlob = blob;
            faceStatus.className = 'step-badge';
            faceStatus.style.background = 'rgba(0, 255, 102, 0.2)';
            faceStatus.style.color = 'var(--accent-neon)';
            faceStatus.textContent = '✓ Rostro Capturado';
            console.log('[RegController] Face photo blob captured.');
        }, 'image/jpeg', 0.95);
    });

    // 3. Record Voice Sample (5 seconds)
    btnRecordVoice.addEventListener('click', () => {
        if (isRecordingVoice || !mediaStream) return;

        isRecordingVoice = true;
        btnRecordVoice.disabled = true;
        voiceStatus.textContent = 'Grabando... (5s)';
        voiceStatus.style.color = 'var(--accent-red)';

        const audioChunks = [];
        const recorder = new MediaRecorder(mediaStream);

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        recorder.onstop = () => {
            capturedVoiceBlob = new Blob(audioChunks, { type: recorder.mimeType || 'audio/webm' });
            audioPreview.src = URL.createObjectURL(capturedVoiceBlob);
            audioPreview.style.display = 'block';

            voiceStatus.style.color = 'var(--accent-neon)';
            voiceStatus.textContent = '✓ Voz Grabada';
            btnRecordVoice.disabled = false;
            isRecordingVoice = false;
        };

        recorder.start();

        // Automatically stop recording after 5 seconds
        setTimeout(() => {
            if (recorder.state === 'recording') {
                recorder.stop();
            }
        }, 5000);
    });

    // 4. Submit Registration Form via AJAX Fetch
    regForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('name-input').value.trim();
        const secretPhrase = document.getElementById('phrase-input').value.trim();

        if (!name || !secretPhrase) {
            alert('Por favor ingresa el nombre y la frase secreta.');
            return;
        }

        if (!capturedFaceBlob) {
            alert('Por favor haz clic en "Tomar Foto del Rostro" antes de guardar.');
            return;
        }

        const formData = new FormData();
        formData.append('name', name);
        formData.append('secret_phrase', secretPhrase);
        formData.append('image', capturedFaceBlob, 'face_capture.jpg');
        if (capturedVoiceBlob) {
            formData.append('audio', capturedVoiceBlob, 'voice_sample.webm');
        }

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        regResponseMsg.style.display = 'block';
        regResponseMsg.className = 'lock-state-banner';
        regResponseMsg.textContent = 'Procesando modelo InsightFace en CPU y guardando en base de datos...';

        try {
            const response = await fetch('/api/register/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData
            });

            const data = await response.json();
            console.log('[RegController] Response:', data);

            if (data.success) {
                regResponseMsg.className = 'lock-state-banner unlocked';
                regResponseMsg.innerHTML = `<strong>${data.message}</strong><br><br><a href="/unlock/" style="color: var(--accent-neon); text-decoration: underline;">Ir a Operar la Cerradura &rarr;</a>`;
                regForm.reset();
                capturedFaceBlob = null;
                capturedVoiceBlob = null;
                faceStatus.textContent = 'No Capturado';
                faceStatus.style.background = 'rgba(255,255,255,0.05)';
                faceStatus.style.color = 'var(--text-muted)';
                voiceStatus.textContent = 'No Grabada';
                audioPreview.style.display = 'none';
            } else {
                regResponseMsg.className = 'lock-state-banner denied';
                regResponseMsg.textContent = data.message || 'Error registrando el usuario.';
            }
        } catch (err) {
            console.error('[RegController] Submit error:', err);
            regResponseMsg.className = 'lock-state-banner denied';
            regResponseMsg.textContent = 'Error de conexión con el servidor Django.';
        }
    });
});
