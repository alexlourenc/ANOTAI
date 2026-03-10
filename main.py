import os
import sounddevice as sd
from scipy.io import wavfile
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Speech-to-Text Integration Added
# Classe Anotai - Adicionada Integração de Speech-to-Text
class Anotai:
    def __init__(self, meeting_name):
        # Load credentials and environment settings
        # Carrega credenciais e configurações de ambiente
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        self.meeting_name = meeting_name
        self.sample_rate = 44100
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self._setup_environment()
        
        self.audio_path = os.path.join(self.recordings_dir, f"{meeting_name.lower().replace(' ', '_')}.wav")
        self.transcription = ""

    def _setup_environment(self):
        # Folder management for data integrity
        # Gestão de pastas para integridade dos dados
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)

    def record_audio(self, duration_seconds=10):
        # Physical audio capture logic
        # Lógica de captura física de áudio
        print(f"[Anotai] Gravando áudio por {duration_seconds}s...")
        recording = sd.rec(int(duration_seconds * self.sample_rate), 
                           samplerate=self.sample_rate, channels=1)
        sd.wait()
        wavfile.write(self.audio_path, self.sample_rate, recording)
        print(f"[Anotai] Áudio capturado: {self.audio_path}")
        return self.audio_path

    def transcribe_audio(self):
        # Sends audio file to OpenAI Whisper for transcription
        # Envia o arquivo de áudio para o OpenAI Whisper para transcrição
        print(f"[Anotai] Iniciando transcrição com IA...")
        
        try:
            with open(self.audio_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    language="pt" # Optimized for Brazilian Portuguese / Otimizado para PT-BR
                )
                self.transcription = transcript.text
                print(f"[Anotai] Transcrição concluída com sucesso.")
                return self.transcription
        except Exception as e:
            print(f"[Anotai] Erro na transcrição: {e}")
            return None

# Main Execution Loop
# Loop de Execução Principal
if __name__ == "__main__":
    app = Anotai("Discussao de Escopo")
    
    # Phase 2: Record / Fase 2: Gravar
    app.record_audio(duration_seconds=10)
    
    # Phase 3: Transcribe / Fase 3: Transcrever
    texto_bruto = app.transcribe_audio()
    
    if texto_bruto:
        print(f"\n--- Texto Transcrito ---\n{texto_bruto}\n")