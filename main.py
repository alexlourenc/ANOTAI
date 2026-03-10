import os
import streamlit as st
import datetime
import json
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Phase 6: Chronological Ordering
# Classe Anotai - Fase 6: Ordenação Cronológica
class Anotai:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            st.error("ERRO: OPENAI_API_KEY não encontrada.")
            st.stop()
        
        self.client = OpenAI(api_key=self.api_key)
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self.outputs_dir = os.path.join(self.base_dir, "outputs")
        self._setup_environment()

    def _setup_environment(self):
        for path in [self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(path):
                os.makedirs(path)

    def save_recording(self, meeting_name, audio_bytes):
        # Timestamp format: YYYYMMDD_HHMMSS (Perfect for sorting)
        # Formato do Timestamp: YYYYMMDD_HHMMSS (Perfeito para ordenação)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = meeting_name.lower().replace(" ", "_") or "reuniao"
        filename = f"{timestamp}_{clean_name}.wav"
        path = os.path.join(self.recordings_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename

    def list_recordings_detailed(self):
        if not os.path.exists(self.recordings_dir): return []
        
        # Get all wav files / Pega todos os arquivos wav
        files = [f for f in os.listdir(self.recordings_dir) if f.endswith(".wav")]
        
        # IMPORTANT: Sorting reversed to show the most recent first
        # IMPORTANTE: Ordenação reversa para mostrar o mais recente primeiro
        files_sorted = sorted(files, reverse=True)
        
        details = []
        for f in files_sorted:
            parts = f.replace(".wav", "").split("_")
            if len(parts) >= 2:
                # Format date for UI: DD/MM/YYYY
                date_val = f"{parts[0][6:8]}/{parts[0][4:6]}/{parts[0][:4]}"
                # Format time for UI: HH:MM
                time_val = f"{parts[1][:2]}:{parts[1][2:4]}"
                name_val = " ".join(parts[2:]).capitalize() if len(parts) > 2 else "Sem Nome"
                details.append({
                    "id": f, 
                    "nome": name_val, 
                    "data_hora": f"{date_val} {time_val}"
                })
        return details

    def run_transcription(self, file_id):
        file_path = os.path.join(self.recordings_dir, file_id)
        with open(file_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="pt"
            )
            return response.text

    def run_llm_processing(self, text):
        prompt = f"""
        Baseado na transcrição: '{text}'
        Gere os formatos:
        1. PAUTA: Tópicos principais e decisões.
        2. CHAT: Resumo executivo para WhatsApp/Slack.
        3. JIRA STORY: Histórias de usuário técnicas.
        """
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um assistente sênior de TI."},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

def main():
    st.set_page_config(page_title="Anotai - Ordenado", page_icon="🎙️", layout="wide")
    app = Anotai()

    st.title("🎙️ Anotai - Gestão Cronológica")
    
    # Recording / Gravação
    st.subheader("🔴 Nova Gravação")
    meeting_name = st.text_input("Nome da Reunião:", placeholder="Ex: Daily, Review...")
    audio_out = mic_recorder(start_prompt="Gravar", stop_prompt="Salvar", key='recorder_sorted')
    
    if audio_out:
        if st.session_state.get('last_h') != hash(audio_out['bytes']):
            app.save_recording(meeting_name, audio_out['bytes'])
            st.session_state.last_h = hash(audio_out['bytes'])
            st.rerun()

    st.divider()

    # Management Table / Tabela de Gestão
    st.subheader("📁 Histórico (Mais recentes no topo)")
    reunioes = app.list_recordings_detailed()
    
    if not reunioes:
        st.info("Nenhuma gravação encontrada.")
    else:
        # Table Header
        h1, h2, h3 = st.columns([3, 2, 1])
        h1.write("**Reunião**")
        h2.write("**Data e Hora**")
        h3.write("**Ação**")

        for r in reunioes:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(r['nome'])
            c2.write(r['data_hora'])
            if c3.button("Processar ⚙️", key=f"btn_{r['id']}"):
                st.session_state.active_file = r['id']
                st.session_state.active_name = r['nome']

    # Results / Resultados
    if 'active_file' in st.session_state:
        st.divider()
        st.subheader(f"📊 Resultado: {st.session_state.active_name}")
        
        cache_path = os.path.join(app.outputs_dir, st.session_state.active_file.replace(".wav", ".json"))
        
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_text, result_text = data["raw"], data["result"]
                st.info("♻️ Resultado carregado do histórico local.")
        else:
            try:
                with st.status("Processando Inteligência Artificial...") as status:
                    raw_text = app.run_transcription(st.session_state.active_file)
                    result_text = app.run_llm_processing(raw_text)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump({"raw": raw_text, "result": result_text}, f, ensure_ascii=False, indent=4)
                    status.update(label="Concluído!", state="complete")
            except Exception as e:
                st.error(f"Erro: {e}")
                st.stop()

        t1, t2 = st.tabs(["📋 Resultados Sugeridos", "📄 Transcrição Bruta"])
        with t1: st.markdown(result_text)
        with t2: st.text_area("Texto capturado:", raw_text, height=300)

if __name__ == "__main__":
    main()