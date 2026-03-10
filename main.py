import os
import sounddevice as sd
from scipy.io import wavfile
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Multi-format Intelligence Added
# Classe Anotai - Adicionada Inteligência Multi-formato
class Anotai:
    def __init__(self, meeting_name):
        load_dotenv()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.meeting_name = meeting_name
        self.sample_rate = 44100
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self.outputs_dir = os.path.join(self.base_dir, "outputs")
        self._setup_environment()
        
        self.audio_path = os.path.join(self.recordings_dir, f"{meeting_name.lower().replace(' ', '_')}.wav")

    def _setup_environment(self):
        # Ensure folders for audio and output text exist
        # Garante que as pastas para áudio e texto de saída existam
        for directory in [self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def record_audio(self, duration_seconds=10):
        print(f"[Anotai] Gravando por {duration_seconds}s...")
        recording = sd.rec(int(duration_seconds * self.sample_rate), samplerate=self.sample_rate, channels=1)
        sd.wait()
        wavfile.write(self.audio_path, self.sample_rate, recording)
        return self.audio_path

    def transcribe_audio(self):
        print(f"[Anotai] Transcrevendo...")
        with open(self.audio_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="pt"
            )
            return transcript.text

    def generate_structured_outputs(self, text):
        # Central logic to create the three specific formats
        # Lógica central para criar os três formatos específicos
        print(f"[Anotai] Gerando formatos: Pauta, Chat e Jira...")
        
        prompt = f"""
        Abaixo está a transcrição de uma reunião chamada '{self.meeting_name}'.
        Extraia as informações e gere 3 formatos distintos:
        
        1. PAUTA ESTRUTURADA: Tópicos principais, decisões e participantes mencionados.
        2. RESUMO PARA CHAT: Um parágrafo curto e direto para Slack/Teams.
        3. JIRA USER STORIES: Transforme requisitos ou ações em histórias de usuário (Eu como..., quero..., para...).
        
        Transcrição:
        {text}
        """

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Você é um assistente sênior de gestão de projetos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        result = response.choices[0].message.content
        self._save_output(result)
        return result

    def _save_output(self, content):
        # Save the final results to a markdown file
        # Salva os resultados finais em um arquivo markdown
        output_path = os.path.join(self.outputs_dir, f"{self.meeting_name.lower().replace(' ', '_')}_resumo.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Anotai] Resumos salvos em: {output_path}")

# Full Execution Flow
# Fluxo de Execução Completo
if __name__ == "__main__":
    app = Anotai("Sprint Review Março")
    
    # app.record_audio(duration_seconds=30) # Descomente para gravar / Uncomment to record
    # text = app.transcribe_audio()
    
    # Exemplo com texto simulado para teste de prompt
    test_text = "Nesta reunião decidimos que o João vai criar a tela de login e a Maria vai configurar o banco de dados até sexta-feira."
    final_output = app.generate_structured_outputs(test_text)
    print("\n" + final_output)