import os
import sounddevice as sd
from scipy.io import wavfile
from dotenv import load_dotenv

# Main class for Anotai - Audio Recording Logic Added
# Classe principal do Anotai - Adicionada lógica de gravação de áudio
class Anotai:
    def __init__(self, meeting_name):
        # Environment and path setup
        # Configuração de ambiente e caminhos
        load_dotenv()
        self.meeting_name = meeting_name
        self.sample_rate = 44100  # Standard CD quality / Qualidade padrão de CD
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self._setup_environment()
        
        self.audio_path = os.path.join(self.recordings_dir, f"{meeting_name.lower().replace(' ', '_')}.wav")

    def _setup_environment(self):
        # Creates data structure if missing
        # Cria a estrutura de dados se estiver faltando
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)

    def record_audio(self, duration_seconds=10):
        # Captures audio from the default microphone
        # Captura áudio do microfone padrão
        print(f"[Anotai] Gravando por {duration_seconds} segundos...")
        
        # Start recording / Inicia a gravação
        recording = sd.rec(int(duration_seconds * self.sample_rate), 
                           samplerate=self.sample_rate, channels=1)
        
        sd.wait()  # Wait until recording is finished / Aguarda a gravação terminar
        
        # Save the file / Salva o arquivo
        wavfile.write(self.audio_path, self.sample_rate, recording)
        print(f"[Anotai] Áudio salvo com sucesso em: {self.audio_path}")
        return self.audio_path

# Application Flow
# Fluxo da Aplicação
if __name__ == "__main__":
    # Example usage / Exemplo de uso
    app = Anotai("Discussao de Requisitos")
    
    # Recording 5 seconds for testing
    # Gravando 5 segundos para teste
    app.record_audio(duration_seconds=5)