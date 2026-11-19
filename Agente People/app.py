import streamlit as st
from agent import executar_agente_rh

st.set_page_config(
    page_title="Agente People - Recrutamento & Seleção",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Agente People IA")
st.subheader("Assistente de Recrutamento e Agendamento de Entrevistas")
st.write(
    "Digite as informações do candidato e da entrevista para agendar no Google Calendar (com Meet) "
    "e registrar os dados na planilha."
)

if "mensagens" not in st.session_state:
    st.session_state["mensagens"] = []

for msg in st.session_state["mensagens"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Agende a entrevista do candidato João Silva (joao@email.com) para a vaga de Dev Python amanhã das 14h às 15h."):
    st.session_state["mensagens"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("O agente está a processar a solicitação..."):
            respostas = executar_agente_rh(prompt)

            for tipo, conteudo in respostas:
                if tipo == "erro":
                    st.error(f"⚠️ Erro: {conteudo}")
                elif tipo == "agendamento":
                    st.success(f"📅 {conteudo}")
                elif tipo == "planilha":
                    st.info(f"📊 {conteudo}")
                else:
                    st.markdown(conteudo)

                st.session_state["mensagens"].append({"role": "assistant", "content": conteudo})