import os
import streamlit as st
import datetime
import json
import pytz
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI

# Anotai Class - Phase 17: Exclusive Admin User Registration
# Classe Anotai - Fase 17: Cadastro de Usuários Exclusivo para Administrador
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
        for path in [self.base_dir, self.recordings_dir, self.outputs_dir]:
            if not os.path.exists(path):
                os.makedirs(path)
        
        if not os.path.exists(self.users_file):
            # First Admin Creation / Criação do primeiro Admin
            self.save_users({
                "admin": {
                    "password": "admin123", 
                    "role": "Administrador",
                    "system_prompt": "Você é um assistente sênior de TI especializado em engenharia de dados.",
                    "user_script": "Analise a transcrição abaixo e gere três seções claras:\n1. PAUTA\n2. CHAT\n3. JIRA STORY"
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
                    details.append({
                        "id": f, "nome": name_val, "data_hora": f"{date_val} {time_val}", "autor": owner
                    })
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

def main():
    st.set_page_config(page_title="Anotai - Gestão Admin", page_icon="🎙️", layout="wide")
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
        st.sidebar.info(f"Perfil: {st.session_state.user_role}")
        if st.sidebar.button("Sair (Logout)"):
            st.session_state.clear()
            st.rerun()

        # Tabs restricted by role / Abas restritas por perfil
        tabs_list = ["🚀 Aplicativo"]
        if st.session_state.user_role == "Administrador":
            tabs_list.append("👥 Gestão de Usuários")
        
        tabs = st.tabs(tabs_list)

        # APPLICATION TAB
        with tabs[0]:
            st.subheader("🔴 Nova Gravação")
            m_name = st.text_input("Título da Reunião:")
            audio_out = mic_recorder(start_prompt="Gravar", stop_prompt="Salvar", key='rec_v17_final')
            if audio_out:
                if st.session_state.get('last_h') != hash(audio_out['bytes']):
                    app.save_recording(m_name, audio_out['bytes'], st.session_state.user_name)
                    st.session_state.last_h = hash(audio_out['bytes'])
                    st.rerun()

            st.divider()
            reunioes = app.list_recordings_detailed(st.session_state.user_name, st.session_state.user_role)
            cols_sizes = [2, 2, 2, 1, 1] if st.session_state.user_role == "Administrador" else [3, 2, 1]
            for r in reunioes:
                c = st.columns(cols_sizes)
                c[0].write(r['nome'])
                c[1].write(r['data_hora'])
                if st.session_state.user_role == "Administrador":
                    c[2].write(f"👤 {r['autor']}")
                    if c[3].button("⚙️", key=f"btn_{r['id']}"): 
                        st.session_state.active_file, st.session_state.active_owner = r['id'], r['autor']
                    if c[4].button("🗑️", key=f"del_{r['id']}"):
                        app.delete_recording(r['id'])
                        st.rerun()
                else:
                    if c[2].button("⚙️", key=f"btn_{r['id']}"): 
                        st.session_state.active_file, st.session_state.active_owner = r['id'], r['autor']

            if 'active_file' in st.session_state:
                st.divider()
                raw, result, is_cached = app.run_full_process(st.session_state.active_file, st.session_state.active_owner)
                res_tab1, res_tab2 = st.tabs(["📋 Inteligência Artificial", "📄 Transcrição na Íntegra"])
                with res_tab1:
                    if is_cached: st.caption("♻️ Recuperado do cache.")
                    st.markdown(result)
                with res_tab2:
                    st.text_area("Original:", value=raw, height=300)

        # ADMIN TAB (Registration and User Scripts)
        if st.session_state.user_role == "Administrador":
            with tabs[1]:
                st.subheader("👥 Cadastro e Gestão de Novos Usuários")
                users = app.load_users()
                
                # Registration/Edit Form / Formulário de Cadastro/Edição
                u_to_edit = st.selectbox("Selecione um usuário para editar ou 'Novo Usuário':", ["Novo Usuário"] + list(users.keys()))
                
                is_new = u_to_edit == "Novo Usuário"
                
                with st.form("user_management_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nu = st.text_input("Usuário (Login)", value="" if is_new else u_to_edit, disabled=not is_new)
                        np = st.text_input("Senha", type="password", value="" if is_new else users[u_to_edit]["password"])
                    with col2:
                        nr = st.selectbox("Perfil de Acesso", ["Usuário", "Administrador"], 
                                          index=0 if is_new or users[u_to_edit]["role"] == "Usuário" else 1)
                    
                    st.divider()
                    st.write("🤖 **Configuração do Script de IA Individual**")
                    n_sys = st.text_area("System Prompt (Personalidade):", 
                                         value="" if is_new else users[u_to_edit].get("system_prompt", ""))
                    n_usr = st.text_area("User Script (Instruções de Saída):", 
                                         value="" if is_new else users[u_to_edit].get("user_script", ""), height=150)
                    
                    if st.form_submit_button("💾 Salvar Cadastro/Alteração"):
                        if nu and np:
                            users[nu] = {"password": np, "role": nr, "system_prompt": n_sys, "user_script": n_usr}
                            app.save_users(users)
                            st.success(f"Usuário {nu} cadastrado/atualizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Por favor, preencha o Usuário e a Senha.")

                st.divider()
                st.write("### Lista de Usuários Ativos")
                for username, info in users.items():
                    c_list = st.columns([3, 2, 1])
                    c_list[0].write(f"**{username}** ({info['role']})")
                    c_list[1].write("✅ Script Configurado" if info.get("user_script") else "⚠️ Script Padrão")
                    if username != st.session_state.user_name:
                        if c_list[2].button("🗑️ Excluir", key=f"del_user_{username}"):
                            del users[username]
                            app.save_users(users)
                            st.rerun()

if __name__ == "__main__":
    main()