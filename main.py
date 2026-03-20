import os
import streamlit as st
import datetime
import pytz
import pandas as pd
import io
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv
from openai import OpenAI
# Importação do banco e do GridFS / Database and GridFS import
from database import db, fs

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
        
        # Coleções e Referências MongoDB / MongoDB Collections and References
        self.db = db
        self.users_col = db['users'] if db is not None else None
        self.meetings_col = db['meetings'] if db is not None else None
        self.fs = fs
        
        self.tz = pytz.timezone("America/Sao_Paulo")
        self._setup_environment()

    def _setup_environment(self):
        # Cria admin inicial com a nova estrutura de scripts / Creates initial admin with new scripts structure
        if self.users_col is not None:
            try:
                if self.users_col.count_documents({}) == 0:
                    self.save_user("admin", {
                        "password": "admin123", 
                        "role": "Administrador",
                        "scripts": {
                            "Padrão": {
                                "system_prompt": "Você é um assistente sênior.",
                                "user_script": "Gere PAUTA, CHAT e JIRA STORY."
                            }
                        }
                    })
            except Exception as e:
                print(f"Erro ao inicializar banco: {e}")

    def load_users(self):
        """Busca todos os usuários e garante a estrutura de scripts / Fetches all users and ensures scripts structure"""
        if self.users_col is None:
            return {}
        try:
            users_dict = {}
            for u in self.users_col.find({}):
                username = u['username']
                # Garante retrocompatibilidade para usuários antigos / Ensures backward compatibility for old users
                if "scripts" not in u:
                    u["scripts"] = {
                        "Geral": {
                            "system_prompt": u.get("system_prompt", ""),
                            "user_script": u.get("user_script", "")
                        }
                    }
                users_dict[username] = u
            return users_dict
        except:
            return {}

    def save_user(self, username, user_data):
        """Salva ou atualiza usuário no DB / Saves or updates user in DB"""
        if self.users_col is not None:
            user_data['username'] = username
            self.users_col.update_one({"username": username}, {"$set": user_data}, upsert=True)

    def delete_user(self, username):
        """Remove usuário do DB / Removes user from DB"""
        if self.users_col is not None:
            self.users_col.delete_one({"username": username})

    def save_recording(self, meeting_name, audio_bytes, user_name):
        """Salva áudio no GridFS / Saves audio in GridFS"""
        if self.fs is not None:
            now_br = datetime.datetime.now(self.tz)
            timestamp = now_br.strftime("%Y%m%d_%H%M%S")
            clean_name = meeting_name.lower().replace(" ", "_") or "reuniao"
            filename = f"{user_name}@{timestamp}_{clean_name}.webm"
            self.fs.put(audio_bytes, filename=filename, metadata={"owner": user_name})
            return filename
        return None

    def delete_recording(self, file_id):
        """Remove áudio e metadados / Removes audio and metadata"""
        if self.fs is not None:
            file_doc = self.fs.find_one({"filename": file_id})
            if file_doc: self.fs.delete(file_doc._id)
        if self.meetings_col is not None:
            self.meetings_col.delete_one({"file_id": file_id})

    def list_recordings_detailed(self, user_name, user_role):
        """Lista gravações do GridFS / Lists recordings from GridFS"""
        if self.fs is None: return []
        details = []
        try:
            files = self.fs.find()
            for f in files:
                filename = f.filename
                if "@" in filename:
                    owner, rest = filename.split("@", 1)
                    if user_role == "Administrador" or owner == user_name:
                        parts = rest.replace(".webm", "").replace(".wav", "").split("_")
                        date_val = f"{parts[0][6:8]}/{parts[0][4:6]}/{parts[0][:4]}"
                        time_val = f"{parts[1][:2]}:{parts[1][2:4]}"
                        name_val = " ".join(parts[2:]).capitalize() if len(parts) > 2 else "Sem Nome"
                        details.append({"id": filename, "nome": name_val, "data_hora": f"{date_val} {time_val}", "autor": owner})
        except:
            pass
        return sorted(details, key=lambda x: x['id'], reverse=True)

    def get_meeting_data(self, file_id):
        """Busca os dados da reunião no banco / Fetches meeting data from DB"""
        if self.meetings_col is None: return {}
        return self.meetings_col.find_one({"file_id": file_id}) or {}

    def transcribe_audio(self, file_id, owner_name):
        """Apenas transcreve e salva no banco / Only transcribes and saves to DB"""
        grid_out = self.fs.find_one({"filename": file_id})
        if not grid_out: 
            return "Arquivo de áudio não encontrado no banco."

        try:
            audio_buffer = io.BytesIO(grid_out.read())
            audio_buffer.name = file_id 
            
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_buffer, 
                language="pt"
            )
            raw_text = transcript.text

            self.meetings_col.update_one(
                {"file_id": file_id},
                {"$set": {
                    "file_id": file_id, 
                    "owner": owner_name, 
                    "raw": raw_text, 
                    "created_at": datetime.datetime.now(self.tz)
                }},
                upsert=True
            )
            return raw_text
        except Exception as e:
            return f"Erro na transcrição: {e}"

    def analyze_text(self, file_id, owner_name, script_name):
        """Lê a transcrição e aplica o script selecionado / Reads transcription and applies selected script"""
        doc = self.get_meeting_data(file_id)
        raw_text = doc.get("raw", "")
        
        if not raw_text:
            return "Erro: Nenhuma transcrição encontrada para analisar."

        users = self.load_users()
        u_data = users.get(owner_name, {})
        
        # Seleciona o script específico do dicionário do usuário / Selects specific script from user dictionary
        scripts_dict = u_data.get("scripts", {})
        selected_script = scripts_dict.get(script_name, {})
        
        sys_p = selected_script.get("system_prompt", "Você é um assistente sênior.")
        usr_s = selected_script.get("user_script", "Resuma a transcrição a seguir.")

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": sys_p}, 
                    {"role": "user", "content": f"{usr_s}\n\nTranscrição: {raw_text}"}
                ]
            )
            result_text = response.choices[0].message.content

            self.meetings_col.update_one(
                {"file_id": file_id},
                {"$set": {"result": result_text}}
            )
            return result_text
        except Exception as e:
            return f"Erro na análise: {e}"

    def convert_to_jira_csv(self, ai_text):
        df = pd.DataFrame({"Summary": ["Anotai Export"], "Description": [ai_text], "Issue Type": ["Story"]})
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()

def main():
    st.set_page_config(page_title="Anotai - Gravação Inteligente", page_icon="🎙️", layout="wide")
    app = Anotai()

    if app.db is None:
        st.error("⚠️ Operando sem Banco de Dados Online. Verifique o MONGODB_URI.")

    if "logged_in" not in st.session_state:
        st.title("🔐 Login - Anotai")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            users = app.load_users()
            if not users and u == "admin" and p == "admin123":
                 st.session_state.update({"logged_in": True, "user_role": "Administrador", "user_name": u})
                 st.rerun()
            elif u in users and users[u]["password"] == p:
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
                audio_out = mic_recorder(start_prompt="🎤 Iniciar Gravação", stop_prompt="💾 Parar e Salvar", key='rec_v22')
            
            with col_rec2:
                if audio_out:
                    st.success("✅ Áudio capturado e salvo no banco!")
                else:
                    st.info("Pronto para gravar.")

            if audio_out and app.db is not None:
                if st.session_state.get('last_h') != hash(audio_out['bytes']):
                    app.save_recording(m_name, audio_out['bytes'], st.session_state.user_name)
                    st.session_state.last_h = hash(audio_out['bytes'])
                    st.rerun()

            st.divider()
            st.subheader("📁 Histórico de Arquivos")
            reunioes = app.list_recordings_detailed(st.session_state.user_name, st.session_state.user_role)
            cols_sizes = [2, 2, 2, 1, 1] if st.session_state.user_role == "Administrador" else [3, 2, 1]
            
            for r in reunioes:
                c = st.columns(cols_sizes)
                c[0].write(f"**{r['nome']}**")
                c[1].write(r['data_hora'])
                if st.session_state.user_role == "Administrador":
                    c[2].write(f"👤 {r['autor']}")
                    if c[3].button("📂 Abrir", key=f"btn_{r['id']}"): 
                        st.session_state.active_file, st.session_state.active_owner = r['id'], r['autor']
                    if c[4].button("🗑️", key=f"del_{r['id']}"):
                        app.delete_recording(r['id'])
                        st.session_state.pop('active_file', None)
                        st.rerun()
                else:
                    if c[2].button("📂 Abrir", key=f"btn_{r['id']}"): 
                        st.session_state.active_file, st.session_state.active_owner = r['id'], r['autor']

            if 'active_file' in st.session_state:
                st.divider()
                st.subheader(f"Gerenciamento: {st.session_state.active_file}")
                
                doc = app.get_meeting_data(st.session_state.active_file)
                raw_text = doc.get("raw", "")
                result_text = doc.get("result", "")

                # Etapa 1: Transcrição / Step 1: Transcription
                if not raw_text:
                    st.warning("O áudio ainda não foi transcrito.")
                    if st.button("📝 Gerar Transcrição do Áudio", type="primary"):
                        with st.spinner("Transcrevendo áudio..."):
                            app.transcribe_audio(st.session_state.active_file, st.session_state.active_owner)
                            st.rerun()
                else:
                    st.success("✅ Transcrição concluída e salva no banco.")
                    with st.expander("Ver Transcrição Original"):
                        st.write(raw_text)
                    
                    # Etapa 2: Análise de IA / Step 2: AI Analysis
                    if not result_text:
                        st.info("A transcrição está pronta para ser analisada pela IA.")
                        
                        # Carrega os scripts disponíveis do usuário / Loads available scripts for the user
                        current_user_data = app.load_users().get(st.session_state.active_owner, {})
                        available_scripts = current_user_data.get("scripts", {"Geral": {}})
                        script_choices = list(available_scripts.keys())
                        
                        # Menu suspenso para escolher qual script rodar / Dropdown menu to choose which script to run
                        selected_script_to_run = st.selectbox("Escolha o Perfil de Análise:", script_choices)
                        
                        if st.button("🤖 Gerar Análise com IA", type="primary"):
                            with st.spinner("Analisando com GPT-4o..."):
                                app.analyze_text(st.session_state.active_file, st.session_state.active_owner, selected_script_to_run)
                                st.rerun()
                    else:
                        st.success("✅ Análise de IA concluída.")
                        
                        st.write("### 📤 Opções de Exportação")
                        st.download_button("📥 Jira CSV", data=app.convert_to_jira_csv(result_text), file_name=f"jira_{st.session_state.active_file}.csv")

                        st.markdown("### Resultado da IA")
                        st.markdown(result_text)

        if st.session_state.user_role == "Administrador":
            with tabs[1]:
                st.subheader("👥 Gestão de Usuários e Scripts")
                users = app.load_users()
                
                # Seletor de usuário isolado para atualizar a tela rapidamente / Isolated user selector to update screen quickly
                u_to_edit = st.selectbox("Selecione o Usuário:", ["Novo Usuário"] + list(users.keys()))
                is_new = u_to_edit == "Novo Usuário"
                user_info = users.get(u_to_edit, {}) if not is_new else {}

                user_scripts = user_info.get("scripts", {"Geral": {"system_prompt": "", "user_script": ""}})
                script_options = ["Novo Script"] + list(user_scripts.keys())
                selected_script_edit = st.selectbox("Selecione o Script para Editar:", script_options)
                is_new_script = selected_script_edit == "Novo Script"
                
                with st.form("edit_user_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nu = st.text_input("Usuário", value="" if is_new else u_to_edit, disabled=not is_new)
                        np = st.text_input("Senha", type="password", value="" if is_new else user_info.get("password", ""))
                    with col2:
                        nr = st.selectbox("Perfil", ["Usuário", "Administrador"], index=0 if is_new or user_info.get("role") == "Usuário" else 1)
                    
                    st.divider()
                    st.write("### Configuração do Script")
                    
                    script_name = st.text_input("Nome do Script (Ex: Reunião, Tarefa):", value="" if is_new_script else selected_script_edit)
                    current_sys = "" if is_new_script else user_scripts[selected_script_edit].get("system_prompt", "")
                    current_usr = "" if is_new_script else user_scripts[selected_script_edit].get("user_script", "")
                    
                    n_sys = st.text_area("System Prompt:", value=current_sys)
                    n_usr = st.text_area("User Script:", value=current_usr, height=200)
                    
                    if st.form_submit_button("💾 Salvar Usuário e Script"):
                        if nu and np and script_name:
                            # Cria uma cópia dos scripts e atualiza com o novo ou editado / Copies scripts and updates with new or edited
                            updated_scripts = user_scripts.copy()
                            updated_scripts[script_name] = {"system_prompt": n_sys, "user_script": n_usr}
                            
                            app.save_user(nu, {"password": np, "role": nr, "scripts": updated_scripts})
                            st.success("Dados atualizados no MongoDB!")
                            st.rerun()

                st.divider()
                st.write("### 📜 Usuários Cadastrados")
                for u, info in users.items():
                    c_list = st.columns([2, 2, 1])
                    qtd_scripts = len(info.get('scripts', {}))
                    c_list[0].write(f"**{u}** ({info.get('role', 'N/A')})")
                    c_list[1].write(f"📑 {qtd_scripts} Script(s)")
                    if u != st.session_state.user_name:
                        if c_list[2].button("🗑️", key=f"del_u_{u}"):
                            app.delete_user(u)
                            st.rerun()

if __name__ == "__main__":
    main()