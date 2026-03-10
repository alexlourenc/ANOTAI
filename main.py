import os
import streamlit as st
import datetime
import json
import pytz # New dependency for timezone / Nova dependência para fuso horário
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Phase 10: Brazilian Timezone Configuration
# Classe Anotai - Fase 10: Configuração de Fuso Horário Brasileiro
class Anotai:
    def __init__(self):
        if os.path.exists(".env"):
            load_dotenv()
        
        self.api_key = None
        try:
            if "OPENAI_API_KEY" in st.secrets:
                self.api_key = st.secrets["OPENAI_API_KEY"]
        except:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            st.error("🔑 API Key não encontrada!")
            st.stop()
        
        self.client = OpenAI(api_key=self.api_key)
        self.base_dir = "data"
        self.recordings_dir = os.path.join(self.base_dir, "recordings")
        self.outputs_dir = os.path.join(self.base_dir, "outputs")
        self.config_file = os.path.join(self.base_dir, "ai_config.json")
        # Define Brazil Timezone / Define Fuso Horário do Brasil
        self.tz = pytz.timezone("America/Sao_Paulo")
        self._setup_environment()

    def _setup_environment(self):
        for path in [self.base_dir, self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(path):
                os.makedirs(path)
        
        if not os.path.exists(self.config_file):
            default_config = {
                "system_prompt": "Você é um assistente sênior de TI especializado em engenharia de dados.",
                "user_script": "Analise a transcrição abaixo e gere três seções claras:\n1. PAUTA: Tópicos principais.\n2. CHAT: Resumo executivo.\n3. JIRA STORY: User Stories técnicas."
            }
            self.save_config(default_config)

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, config_data):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

    def save_recording(self, meeting_name, audio_bytes):
        # Get current time in Brazil / Pega a hora atual no Brasil
        now_br = datetime.datetime.now(self.tz)
        timestamp = now_br.strftime("%Y%m%d_%H%M%S")
        
        clean_name = meeting_name.lower().replace(" ", "_") or "reuniao"
        filename = f"{timestamp}_{clean_name}.wav"
        path = os.path.join(self.recordings_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename

    def delete_recording(self, file_id):
        audio_path = os.path.join(self.recordings_dir, file_id)
        json_path = os.path.join(self.outputs_dir, file_id.replace(".wav", ".json"))
        
        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(json_path):
            os.remove(json_path)
        
        if st.session_state.get('active_file') == file_id:
            del st.session_state.active_file
            del st.session_state.active_name

    def list_recordings_detailed(self):
        if not os.path.exists(self.recordings_dir): return []
        files = [f for f in os.listdir(self.recordings_dir) if f.endswith(".wav")]
        files_sorted = sorted(files, reverse=True)
        details = []
        for f in files_sorted:
            parts = f.replace(".wav", "").split("_")
            if len(parts) >= 2:
                # Local formatting / Formatação local
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
        config = self.load_config()

        with open(file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="pt"
            )
            raw_text = transcript.text

        prompt = f"{config['user_script']}\n\nTranscrição: {raw_text}"
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": config['system_prompt']},
                      {"role": "user", "content": prompt}]
        )
        result_text = response.choices[0].message.content

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"raw": raw_text, "result": result_text}, f, ensure_ascii=False, indent=4)

        return raw_text, result_text, False

def main():
    st.set_page_config(page_title="Anotai - BR Time", page_icon="🎙️", layout="wide")
    app = Anotai()

    st.title("🎙️ Anotai - Timezone Brasil")
    
    t_app, t_config = st.tabs(["🚀 Aplicativo", "⚙️ Configurações"])

    with t_app:
        st.subheader("🔴 Nova Gravação")
        m_name = st.text_input("Título da Reunião:", key="main_title")
        audio_out = mic_recorder(start_prompt="Gravar", stop_prompt="Salvar", key='rec_v10')
        
        if audio_out:
            if st.session_state.get('last_h') != hash(audio_out['bytes']):
                app.save_recording(m_name, audio_out['bytes'])
                st.session_state.last_h = hash(audio_out['bytes'])
                st.rerun()

        st.divider()
        st.subheader("📁 Histórico (Horário de Brasília)")
        reunioes = app.list_recordings_detailed()
        
        for r in reunioes:
            c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
            c1.write(r['nome'])
            c2.write(r['data_hora'])
            
            if c3.button("Processar ⚙️", key=f"btn_{r['id']}"):
                st.session_state.active_file = r['id']
                st.session_state.active_name = r['nome']
            
            if c4.button("Apagar 🗑️", key=f"del_{r['id']}"):
                app.delete_recording(r['id'])
                st.rerun()

        if 'active_file' in st.session_state:
            st.divider()
            raw, result, is_cached = app.run_full_process(st.session_state.active_file)
            res_t1, res_t2 = st.tabs(["📋 Resultado", "📄 Transcrição"])
            with res_t1: 
                if is_cached: st.caption("♻️ Recuperado do cache local.")
                st.markdown(result)
            with res_t2: st.text_area("Original:", raw, height=200)

    with t_config:
        st.subheader("🛠️ Script da IA")
        curr = app.load_config()
        n_sys = st.text_area("System Prompt:", value=curr["system_prompt"])
        n_user = st.text_area("User Script:", value=curr["user_script"], height=200)
        if st.button("💾 Salvar Configurações"):
            app.save_config({"system_prompt": n_sys, "user_script": n_user})
            st.success("Salvo com sucesso!")

if __name__ == "__main__":
    main()