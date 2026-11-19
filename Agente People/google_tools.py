import os
import unicodedata
import uuid
from datetime import datetime
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


ARQUIVO_CREDENCIAIS = os.path.join(
    BASE_DIR, "client_secret.json"
)
ARQUIVO_TOKEN = os.path.join(
    BASE_DIR, "token.json"
)
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/spreadsheets',
]

CAMPOS_DA_PLANILHA = {
    "nome": {"nome", "nomecandidato"},
    "vaga": {"vaga", "cargo"},
    "data": {"data", "dataentrevista"},
    "hora": {"hora", "horario", "horarioentrevista"},
    "email": {"email", "emailcandidato"},
    "status": {"status", "situacao"},
}


def autenticar_google():
    """Autentica no Google e retorna as credenciais."""

    credenciais = None

    if os.path.exists(ARQUIVO_TOKEN):
        credenciais = Credentials.from_authorized_user_file(
            ARQUIVO_TOKEN,
            SCOPES
        )

    if credenciais and credenciais.expired and credenciais.refresh_token:
        try:
            credenciais.refresh(Request())
        except RefreshError:
            credenciais = None

    if not credenciais or not credenciais.valid:

        fluxo = InstalledAppFlow.from_client_secrets_file(
            ARQUIVO_CREDENCIAIS,
            SCOPES
        )

        credenciais = fluxo.run_local_server(port=0)

    with open(ARQUIVO_TOKEN, "w", encoding="utf-8") as token:
        token.write(credenciais.to_json())

    return credenciais

def agendar_entrevista_com_meet(
    nome_candidato,
    email_candidato,
    data_hora_inicio,
    data_hora_fim,
):
    """Agenda uma entrevista no Google Calendar com link do Google Meet."""
    servico = build('calendar', 'v3', credentials=autenticar_google())

    evento = {
        "summary": f"Entrevista com {nome_candidato}",
        "description": "Entrevista de alinhamento com o time de People.",
        "start": {
            "dateTime": data_hora_inicio,
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": data_hora_fim,
            "timeZone": "America/Sao_Paulo",
        },
        "attendees": [
            {"email": email_candidato},
        ],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            },
        },
    }

    evento_criado = servico.events().insert(
        calendarId='primary',
        body=evento,
        conferenceDataVersion=1,
        sendUpdates='all',
    ).execute()

    return evento_criado.get("hangoutLink")

def registrar_candidato_planilha(
    id_planilha,
    nome,
    email,
    vaga,
    status,
    data_hora_inicio=None,
    data_hora_fim=None
):
    """Regista os dados do candidato na planilha do Google Sheets."""
    servico = build('sheets', 'v4', credentials=autenticar_google())

    planilha = servico.spreadsheets().get(
        spreadsheetId=id_planilha,
        fields="sheets(properties(sheetId,title))",
    ).execute()

    aba = next(
        (item["properties"]
         for item in planilha.get("sheets", [])
         if item["properties"].get("sheetId") == 0),
        None
    )

    if not aba:
        raise ValueError("Aba principal não encontrada na planilha.")

    resposta = servico.spreadsheets().values().get(
        spreadsheetId=id_planilha,
        range="A1:F1",
    ).execute()

    linhas = resposta.get("values", [])
    cabecalho = linhas[0] if linhas else []

    colunas = {}
    for idx, col in enumerate(cabecalho):
        col_norm = unicodedata.normalize("NFKD", col).encode("ascii", "ignore").decode("utf-8").lower().replace(" ", "")
        for campo, sinonimos in CAMPOS_DA_PLANILHA.items():
            if col_norm in sinonimos:
                colunas[campo] = idx

    dados = {
        "nome": nome,
        "email": email,
        "vaga": vaga,
        "status": status,
    }

    if data_hora_inicio and "data" in colunas:
        try:
            inicio = datetime.fromisoformat(data_hora_inicio)
            dados["data"] = inicio.strftime("%d/%m/%Y")
            if "hora" in colunas:
                hora = inicio.strftime("%H:%M")
                if data_hora_fim:
                    fim = datetime.fromisoformat(data_hora_fim)
                    hora += f" - {fim.strftime('%H:%M')}"
                dados["hora"] = hora
        except ValueError:
            raise ValueError("Formato de data/hora inválido. Use YYYY-MM-DDTHH:MM:SS.")

    valores = [""] * (max(colunas.values()) + 1 if colunas else 6)
    for campo, valor in dados.items():
        if campo in colunas:
            valores[colunas[campo]] = valor

    servico.spreadsheets().values().append(
        spreadsheetId=id_planilha,
        range="A:F",
        valueInputOption="USER_ENTERED",
        body={"values": [valores]},
    ).execute()

    return "Candidato registrado com sucesso na planilha."