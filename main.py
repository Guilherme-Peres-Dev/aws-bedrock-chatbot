import hmac
import os

import boto3
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "mistral.devstral-2-123b")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
MAX_TOKENS = 1000          # limite de tokens por resposta
MAX_HISTORY = 20           # mensagens anteriores enviadas ao modelo

st.set_page_config(page_title="AWS AI Assistant", page_icon="🤖", layout="centered")


# ------------------------------------------------------------------ Login
def check_password() -> bool:
    if not APP_PASSWORD:
        st.error("APP_PASSWORD não está definida no .env.")
        return False

    if st.session_state.get("authenticated"):
        return True

    st.warning("🔒 Acesso restrito. Insira a senha para continuar.")
    pwd_input = st.text_input("Senha", type="password")

    if pwd_input:
        if hmac.compare_digest(pwd_input.encode(), APP_PASSWORD.encode()):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


if not check_password():
    st.stop()


# ---------------------------------------------------------------- Bedrock
@st.cache_resource
def get_client():
    # O boto3 lê AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY do ambiente (.env já carregado)
    return boto3.client("bedrock-runtime", region_name=REGION)


def build_history(messages):
    """Converte o histórico do Streamlit para o formato da Converse API."""
    history = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in messages[-MAX_HISTORY:]
    ]
    # A Converse API exige que a conversa comece com 'user'
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


def get_bedrock_response(messages) -> str:
    response = get_client().converse(
        modelId=MODEL_ID,
        messages=build_history(messages),
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0.5},
    )
    blocks = response["output"]["message"]["content"]
    return "".join(b["text"] for b in blocks if "text" in b)


# ------------------------------------------------------------------- Chat
st.title("🤖 AWS Bedrock AI Assistant")
st.caption("Chatbot inteligente integrado com serviços de IA Generativa da AWS.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Olá! Sou seu assistente de IA hospedado na AWS. Como posso ajudar?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if user_input := st.chat_input("Digite a sua mensagem..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Processando..."):
            try:
                response_text = get_bedrock_response(st.session_state.messages)
                st.write(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except (ClientError, BotoCoreError) as e:
                st.session_state.messages.pop()  # remove a pergunta que falhou
                st.error(f"Erro ao comunicar com a AWS: {e}")