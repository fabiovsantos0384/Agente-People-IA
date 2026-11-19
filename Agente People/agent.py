
import json
import os
import unicodedata

from dotenv import load_dotenv
from openai import OpenAI

from google_tools import (
    agendar_entrevista_com_meet,
    registrar_candidato_planilha
)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PLANILHA_ID = os.getenv("PLANILHA_ID")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
) if GROQ_API_KEY else None

MODELO_GROQ = "openai/gpt-oss-120b"

FERRAMENTAS = [
    {
        "type": "function",
        "function": {
            "name": "agendar_entrevista_com_meet",
            "description": (
                "Agenda a entrevista no Google Calendar com Meet. "
                "Só use quando todos os dados estiverem disponíveis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nome_candidato": {"type": "string"},
                    "email_candidato": {"type": "string"},
                    "vaga": {"type": "string"},
                    "status": {"type": "string"},
                    "data_hora_inicio": {
                        "type": "string",
                        "description": "Data e hora ISO 8601."
                    },
                    "data_hora_fim": {
                        "type": "string",
                        "description": "Data e hora ISO 8601."
                    }
                },
                "required": [
                    "nome_candidato",
                    "email_candidato",
                    "vaga",
                    "status",
                    "data_hora_inicio",
                    "data_hora_fim"
                ]
            }
        }
    }
]

PROMPT = """
Você é o Agente People IA, um assistente de recrutamento.

Sua função é coletar os dados do candidato, agendar entrevistas
no Google Calendar com link do Google Meet e registrar os dados
no Google Sheets.

Antes de agendar, confirme que possui:
- Nome completo do candidato
- E-mail
- Vaga
- Data e horário de início
- Data e horário de término
- Status da candidatura

Se faltar alguma informação, pergunte ao usuário.

Não invente informações.

Quando todos os dados estiverem disponíveis, chame a ferramenta
agendar_entrevista_com_meet.

Use datas no formato ISO 8601:
AAAA-MM-DDTHH:MM:SS

O sistema registrará automaticamente o candidato na planilha
depois que o agendamento for concluído.
"""


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(
        letra for letra in sem_acento
        if not unicodedata.combining(letra)
    ).lower()


def executar_agente_rh(mensagem_usuario):

    if client is None:
        return [
            ("erro", "Configure a chave GROQ_API_KEY no arquivo .env.")
        ]

    if not PLANILHA_ID:
        return [
            ("erro", "Configure o PLANILHA_ID no arquivo .env.")
        ]

    try:
        resposta = client.chat.completions.create(
            model=MODELO_GROQ,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": mensagem_usuario}
            ],
            tools=FERRAMENTAS,
            tool_choice="auto"
        )

        mensagem = resposta.choices[0].message
        tool_calls = mensagem.tool_calls or []

        resultados = []

        if not tool_calls:
            resultados.append((
                "texto",
                mensagem.content or "Não foi possível obter uma resposta."
            ))
            return resultados

        for chamada in tool_calls:

            nome_funcao = chamada.function.name
            args = json.loads(chamada.function.arguments)

            if nome_funcao == "agendar_entrevista_com_meet":

                # Primeiro: agenda a entrevista
                try:
                    link_meet = agendar_entrevista_com_meet(
                        nome_candidato=args["nome_candidato"],
                        email_candidato=args["email_candidato"],
                        data_hora_inicio=args["data_hora_inicio"],
                        data_hora_fim=args["data_hora_fim"]
                    )

                    resultados.append((
                        "agendamento",
                        f"Entrevista agendada com sucesso! Link do Meet: {link_meet}"
                    ))

                except Exception as erro:
                    resultados.append((
                        "erro",
                        f"Não foi possível agendar a entrevista: {erro}"
                    ))
                    continue

                # Segundo: registra automaticamente na planilha
                try:
                    msg_planilha = registrar_candidato_planilha(
                        id_planilha=PLANILHA_ID,
                        nome=args["nome_candidato"],
                        email=args["email_candidato"],
                        vaga=args["vaga"],
                        status=args["status"],
                        data_hora_inicio=args["data_hora_inicio"],
                        data_hora_fim=args["data_hora_fim"]
                    )

                    resultados.append((
                        "planilha",
                        msg_planilha
                    ))

                except Exception as erro:
                    resultados.append((
                        "erro",
                        f"A entrevista foi agendada, mas houve um erro ao registrar na planilha: {erro}"
                    ))

        return resultados

    except Exception as erro:
        return [
            ("erro", f"Erro ao executar o agente: {erro}")
        ]
