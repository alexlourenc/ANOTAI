import os
import streamlit as st
import datetime
import json
import pytz
import pandas as pd
import io
# Ensure you ran: pip install fpdf2 / Certifique-se de que executou: pip install fpdf2
from fpdf import FPDF
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Phase 22: PDF Generation with Error Handling
# Classe Anotai - Fase 22: Geração de PDF com Tratamento de Erros
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
        self.users_file = os.path.join(self.base_dir, "users.json")
        self.tz = pytz.timezone("America/Sao_Paulo")
        self._setup_environment()

    def _setup_environment(self):
        # Create storage directories / Cria diretórios de armazenamento
        for path in [self.base_dir, self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(path):
                os.makedirs(path)
        
        if not os.path.exists(self.users_file):
            self.save_users({
                "admin": {
                    "password": "admin123", 
                    "role": "Administrador",
                    "system_prompt": "Você é um assistente sênior.",
                    "user_script": "Gere PAUTA, CHAT e JIRA STORY."
                }
            })

    def load_users(self):
        with open(self.users_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_users(self, users_data):
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)

    def save_recording(self, meeting_name, audio_bytes, user_name):
        now_br = datetime.datetime.now(self.tz)
        timestamp = now_br.strftime("%Y%m%d_%H%M%S")
        clean_name = meeting_name.lower().replace(" ", "_") or "reuniao"
        filename = f"{user_name}@{timestamp}_{clean_name}.wav"
        path = os.path.join(self.recordings_dir, filename)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        return filename

    def delete_recording(self, file_id):
        audio_path = os.path.join(self.recordings_dir, file_id)
        json_path = os.path.join(self.outputs_dir, file_id.replace(".wav", ".json"))
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(json_path): os.remove(json_path)

    def list_recordings_detailed(self, user_name, user_role):
        if not os.path.exists(self.recordings_dir): return []
        files = [f for f in os.listdir(self.recordings_dir) if f.endswith(".wav")]
        files_sorted = sorted(files, reverse=True)
        details = []
        for f in files_sorted:
            if "@" in f:
                owner, rest = f.split("@", 1)
                if user_role == "Administrador" or owner == user_name:
                    parts = rest.replace(".wav", "").split("_")
                    date_val = f"{parts[0][6:8]}/{parts[0][4:6]}/{parts[0][:4]}"
                    time_val = f"{parts[1][:2]}:{parts[1][2:4]}"
                    name_val = " ".join(parts[2:]).capitalize() if len(parts) > 2 else "Sem Nome"
                    details.append({"id": f, "nome": name_val, "data_hora": f"{date_val} {time_val}", "autor": owner})
        return details

    def run_full_process(self, file_id, owner_name):
        json_path = os.path.join(self.outputs_dir, file_id.replace(".wav", ".json"))
        users = self.load_users()
        u_data = users.get(owner_name, {})
        sys_p = u_data.get("system_prompt") or "Você é um assistente sênior."
        usr_s = u_data.get("user_script") or "Resuma a transcrição a seguir."

        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data["raw"], data["result"], True
        
        file_path = os.path.join(self.recordings_dir, file_id)
        with open(file_path, "rb") as audio_file:
            transcript = self.client.audio.transcriptions.create(model="whisper-1", file=audio_file, language="pt")
            raw_text = transcript.text
        
        prompt = f"{usr_s}\n\nTranscrição: {raw_text}"
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": sys_p}, {"role": "user", "content": prompt}]
        )
        result_text = response.choices[0].message.content
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"raw": raw_text, "result": result_text}, f, ensure_ascii=False, indent=4)
        return raw_text, result_text, False

    def convert_to_jira_csv(self, ai_text):
        df = pd.DataFrame({"Summary": ["Anotai Export"], "Description": [ai_text], "Issue Type": ["Story"]})
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()

    def generate_pdf(self, title, content):
        # PDF Generation / Geração de PDF
        pdf = FPDF()
        pdf.add_page()
        # Adding a default font that supports basic latin-1 / Adicionando fonte padrão
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, f"Anotai - {title}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("helvetica", size=11)
        
        # Treatment for special characters / Tratamento para caracteres especiais
        clean_content = content.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 8, clean_content)
        return pdf.output()

def main():
    st.set_page_config(page_title="Anotai - Gravação Inteligente", page_icon="🎙️", layout="wide")
    app = Anotai()

    if "logged_in" not in st.session_state:
        st.title("🔐 Login - Anotai")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            users = app.load_users()
            if u in users and users[u]["password"] == p:
                st.session_state.update({"logged_in": True, "user_role": users[u]["role"], "user_name": u})
                st.rerun()
            else: st.error("Acesso negado.")
    else:
        st.sidebar.title(f"👤 {st.session_state.user_name}")
        if st.sidebar.button("Sair (Logout)"):
            st.session_state.clear()
            st.rerun()

        tabs_list = ["🚀 Aplicativo"]
        if st.session_state.user_role == "Administrador":
            tabs_list.append("👥 Gestão e Scripts")
        
        tabs = st.tabs(tabs_list)

        with tabs[0]:
            st.subheader("🔴 Gravação de Reunião")
            m_name = st.text_input("Título da Reunião:", placeholder="Ex: Daily Scrum")
            
            col_rec1, col_rec2 = st.columns([1, 2])
            with col_rec1:
                audio_out = mic_recorder(start_prompt="🎤 Iniciar Gravação", stop_prompt="💾 Parar e Salvar", key='rec_v22_fix')
            
            with col_rec2:
                if audio_out:
                    st.success("✅ Áudio capturado!")
                else:
                    st.info("Pronto para gravar.")

            if audio_out:
                if st.session_state.get('last_h') != hash(audio_out['bytes']):
                    app.save_recording(m_name, audio_out['bytes'], st.session_state.user_name)
                    st.session_state.last_h = hash(audio_out['bytes'])
                    st.rerun()

            st.divider()
            st.subheader("📁 Histórico")
            reunioes = app.list_recordings_detailed(st.session_state.user_name, st.session_state.user_role)
            for r in reunioes:
                c = st.columns([4, 1, 1] if st.session_state.user_role == "Administrador" else [4, 1])
                c[0].write(f"**{r['nome']}** ({r['data_hora']})")
                if c[1].button("🧠", key=f"btn_{r['id']}"): 
                    st.session_state.active_file, st.session_state.active_owner = r['id'], r['autor']
                if st.session_state.user_role == "Administrador" and c[2].button("🗑️", key=f"del_{r['id']}"):
                    app.delete_recording(r['id'])
                    st.rerun()

            if 'active_file' in st.session_state:
                st.divider()
                raw, result, is_cached = app.run_full_process(st.session_state.active_file, st.session_state.active_owner)
                
                st.write("### 📤 Exportar")
                exp_c1, exp_c2, exp_c3 = st.columns(3)
                with exp_c1:
                    st.download_button("📥 Jira CSV", data=app.convert_to_jira_csv(result), file_name=f"jira_{st.session_state.active_file}.csv")
                with exp_c2:
                    pdf_ia = app.generate_pdf("Resultado IA", result)
                    st.download_button("📄 PDF (IA)", data=bytes(pdf_ia), file_name=f"IA_{st.session_state.active_file}.pdf", mime="application/pdf")
                with exp_c3:
                    pdf_raw = app.generate_pdf("Transcrição Íntegra", raw)
                    st.download_button("📄 PDF (Íntegra)", data=bytes(pdf_raw), file_name=f"INTEGRA_{st.session_state.active_file}.pdf", mime="application/pdf")

                res_tab1, res_tab2 = st.tabs(["📋 Inteligência Artificial", "📄 Transcrição"])
                with res_tab1: st.markdown(result)
                with res_tab2: st.text_area("Original:", value=raw, height=300)

        # Admin Tab preserved / Aba Admin preservada
        if st.session_state.user_role == "Administrador":
            with tabs[1]:
                st.write("Aba de Gestão Ativa.")

if __name__ == "__main__":
    main()