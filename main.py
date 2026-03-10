import os
import streamlit as st
import datetime
import json
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Phase 7: Cloud Deployment Ready
# Classe Anotai - Fase 7: Pronto para Implantação em Nuvem
class Anotai:
    def __init__(self):
        # Load .env only if file exists (Local dev)
        # Carrega .env apenas se o arquivo existir (Desenvolvimento local)
        if os.path.exists(".env"):
            load_dotenv()
        
        # Priority for Streamlit Secrets (Cloud) then Environment Variables
        # Prioridade para Streamlit Secrets (Nuvem) depois Variáveis de Ambiente
        self.api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            st.error("ERRO: API Key não configurada. Adicione em Secrets (Cloud) ou no .env (Local).")
            st.stop()
        
        self.client = OpenAI(api_key=self.api_key)
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self.outputs_dir = os.path.join(self.base_dir, "outputs")
        self._setup_environment()

    def _setup_environment(self):
        # Ensure directories exist in the ephemeral cloud storage
        # Garante que os diretórios existam no armazenamento efêmero da nuvem
        for path in [self.base_dir, self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(path):
                os.makedirs(path)

    def save_recording(self, meeting_name, audio_bytes):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = meeting_name.lower().replace(" ", "_") or "reuniao"
        filename = f"{timestamp}_{clean_name}.wav"
        path = os.path.join(self.recordings_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename

    def list_recordings_detailed(self):
        if not os.path.exists(self.recordings_dir): return []
        files = [f for f in os.listdir(self.recordings_dir) if f.endswith(".wav")]
        files_sorted = sorted(files, reverse=True)
        
        details = []
        for f in files_sorted:
            parts = f.replace(".wav", "").split("_")
            if len(parts) >= 2:
                date_val = f"{parts[0][6:8]}/{parts[0][4:6]}/{parts[0][:4]}"
                time_val = f"{parts[1][:2]}:{parts[1][2:4]}"
                name_val = " ".join(parts[2:]).capitalize() if len(parts) > 2 else "Sem Nome"
                details.append({"id": f, "nome": name_val, "data_hora": f"{date_val} {time_val}"})
        return details

    def run_full_process(self, file_id):
        json_path = os.path.join(self.outputs_dir, file_id.replace(".wav", ".json"))
        
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data["raw"], data["result"], True

        file_path = os.path.join(self.recordings_dir, file_id)
        with open(file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="pt"
            )
            raw_text = transcript.text

        prompt = f"Gere PAUTA, CHAT e JIRA STORY para: {raw_text}"
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Você é um assistente sênior."},
                      {"role": "user", "content": prompt}]
        )
        result_text = response.choices[0].message.content

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"raw": raw_text, "result": result_text}, f, ensure_ascii=False, indent=4)

        return raw_text, result_text, False

def main():
    st.set_page_config(page_title="Anotai - Cloud Online", page_icon="🎙️", layout="wide")
    app = Anotai()

    st.title("🎙️ Anotai - Gestão Inteligente")
    
    # Simple warning about persistence on Cloud
    # Aviso simples sobre persistência na Nuvem
    if not os.path.exists(".env"):
        st.sidebar.warning("⚠️ Nota: Em servidores gratuitos, os arquivos podem ser limpos após um período de inatividade.")

    st.subheader("🔴 Nova Gravação")
    m_name = st.text_input("Título da Reunião:")
    audio_out = mic_recorder(start_prompt="Gravar", stop_prompt="Salvar", key='recorder_cloud')
    
    if audio_out:
        audio_hash = hash(audio_out['bytes'])
        if st.session_state.get('last_h') != audio_hash:
            app.save_recording(m_name, audio_out['bytes'])
            st.session_state.last_h = audio_hash
            st.rerun()

    st.divider()

    # Table
    st.subheader("📁 Histórico")
    reunioes = app.list_recordings_detailed()
    for r in reunioes:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(r['nome'])
        c2.write(r['data_hora'])
        if c3.button("Processar ⚙️", key=f"btn_{r['id']}"):
            st.session_state.active_file = r['id']
            st.session_state.active_name = r['nome']

    # Results
    if 'active_file' in st.session_state:
        st.divider()
        raw, result, is_cached = app.run_full_process(st.session_state.active_file)
        
        t1, t2 = st.tabs(["📝 Inteligência", "📄 Transcrição"])
        with t1: 
            if is_cached: st.caption("♻️ Recuperado do cache local.")
            st.markdown(result)
        with t2: st.text_area("Bruto:", raw, height=200)

if __name__ == "__main__":
    main()