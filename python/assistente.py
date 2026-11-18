import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta

import cv2
import edge_tts
import pyttsx3
import requests
import speech_recognition as sr
from groq import Groq
from pygame import mixer

import capturar_rosto

try:
    import serial  # pyserial - só é necessário se for usar o Arduino
    import serial.tools.list_ports
except ImportError:
    serial = None

# No Windows, o backend padrão (MSMF) demora vários segundos pra abrir a
# câmera; o DirectShow abre quase instantâneo. Em Linux/macOS mantemos o
# backend automático, já que CAP_DSHOW só existe no Windows.
BACKEND_CAMERA = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY

# Usado para reconhecer datas faladas por extenso (ex: "dia 15 de setembro")
MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


class Comando:
    """Representa um comando de voz (padrão Command): guarda os gatilhos de
    fala que o ativam e a ação a executar quando reconhecido."""

    def __init__(self, nome, gatilhos, acao):
        self.nome = nome
        self.gatilhos = gatilhos
        self.acao = acao  # função que recebe (texto_comando) e executa a ação

    def bate_com(self, texto_comando):
        """Verifica se algum dos gatilhos deste comando está no texto falado."""
        return any(gatilho in texto_comando for gatilho in self.gatilhos)

    def executar(self, texto_comando):
        self.acao(texto_comando)


class AssistenteVirtual:
    """Encapsula toda a lógica do assistente: ouvir, decidir, agir e falar."""

    # Palavras que ativam a assistente (aceita o nome completo ou o apelido)
    PALAVRAS_ATIVACAO = [
    "lumi",
    "lumibot",
    "lumi bot",
    "lumi bote",
    "lumibote",
    "lume",
    "lumebot",
    "lume bot",
    "lume bote",
    "lumebote",
    "lumi robô",
    "lume robô",
    "lumi robo",
    "lume robo",
    "lumi robot",
    "lume robot",
    "lumi boti",
    "lume boti",
    "lumiboti",
    "lumeboti",
    ]


    # Voz usada pelo edge-tts (voz online principal). Vozes masculinas em pt-BR:
    # "pt-BR-AntonioNeural"; femininas: "pt-BR-FranciscaNeural".
    VOZ_EDGE_TTS = "pt-BR-AntonioNeural"

    # Confiança máxima (quanto menor, mais parecido) pra considerar um rosto
    # reconhecido. Acima disso, é tratado como "desconhecido".
    LIMITE_CONFIANCA_FACE = 4000

    # Limiares do LDR (mais luz = valor menor). Calibre no seu ambiente.
    LIMIAR_ESCURO = 700
    LIMIAR_PENUMBRA = 500

    # Gatilhos de voz aceitos para cada comando (várias formas de falar a mesma coisa)
    GATILHOS_CADASTRAR_EVENTO = ["cadastrar evento", "cadastra um evento", "cadastra evento", "novo evento", "criar evento"]
    GATILHOS_LER_AGENDA = ["ler agenda", "leia a agenda", "ler minha agenda", "mostrar agenda", "quais são meus eventos"]
    GATILHOS_LIMPAR_AGENDA = ["limpar agenda", "apagar a agenda", "apagar agenda", "limpar minha agenda", "zerar agenda"]
    GATILHOS_HORA = ["que horas são", "que horas é", "me diz as horas", "qual é a hora", "que horas"]
    GATILHOS_DATA = ["que dia é hoje", "que dia é", "qual o dia de hoje", "qual a data de hoje", "que dia"]
    GATILHOS_CALCULAR = ["calcular"]
    GATILHOS_RECONHECER_FACE = ["reconhecer face", "quem sou eu", "reconheça minha face", "reconhece minha face"]
    GATILHOS_CADASTRAR_FACE = ["cadastrar rosto", "cadastra um rosto", "cadastra rosto", "novo rosto", "criar rosto"]
    GATILHOS_CLIMA = ["clima", "previsão do tempo", "previsao do tempo", "qual o clima", "vai chover"]
    GATILHOS_LIGAR_LUZ = ["ligar luz", "acender luz", "acende a luz"]
    GATILHOS_DESLIGAR_LUZ = ["desligar luz", "apagar luz", "apaga a luz"]
    GATILHOS_CUMPRIMENTAR = ["olá", "bom dia", "boa tarde", "boa noite", "tudo bem"]
    GATILHOS_VERIFICAR_LUZ = ["como está a luz", "como está a iluminação", "verificar iluminação",
                              "verificar a iluminação", "verificar luz", "analisar iluminação", "iluminação"]
    GATILHOS_RELATORIO = ["relatório", "relatorio"]

    # Operadores aceitos na calculadora por voz (chave -> função)
    OPERADORES = {
        "multiplicado por": lambda a, b: a * b,
        "dividido por": lambda a, b: a / b,
        "mais": lambda a, b: a + b,
        "menos": lambda a, b: a - b,
        "vezes": lambda a, b: a * b,
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "x": lambda a, b: a * b,
        "/": lambda a, b: a / b,
        "elevado": lambda a, b: a ** b,
    }

    def __init__(self, arquivo_agenda="agenda.txt", modelo_facial="classificador_eigen.yml",
                 groq_api_key=None, porta_arduino=None, cidade_padrao="Santo André, São Paulo"):
        # --- Reconhecimento e síntese de voz ---
        self.reconhecedor = sr.Recognizer()
        # pause_threshold: quanto tempo de silêncio o reconhecedor tolera
        # antes de considerar que você terminou de falar. Valor mais alto
        # evita cortar o comando quando você pausa naturalmente depois da
        # palavra de ativação (ex: "Lumi... cadastrar evento").
        self.reconhecedor.pause_threshold = 2.0
        self.reconhecedor.non_speaking_duration = 0.8
        # Ajuste automático do limiar enquanto a pessoa fala: evita que pequenas
        # variações de volume sejam confundidas com o fim da frase.
        self.reconhecedor.dynamic_energy_threshold = True
        self.reconhecedor.dynamic_energy_adjustment_damping = 0.15
        self.reconhecedor.dynamic_energy_adjustment_ratio = 1.5
        self.microfone_calibrado = False

        self.motor_voz_offline = pyttsx3.init()
        self.motor_voz_offline.setProperty("rate", 180)
        self.motor_voz_offline.setProperty("volume", 1.0)
        mixer.init()  # usado pela voz online (edge-tts), que é a voz principal

        # --- Agenda ---
        self.arquivo_agenda = arquivo_agenda

        # --- IA generativa (Groq) ---
        self.groq_client = Groq(api_key=groq_api_key or os.environ.get("GROQ_API_KEY"))

        # --- Reconhecimento facial ---
        self.classificador_face = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.modelo_facial = modelo_facial
        self.reconhecedor_facial = cv2.face.EigenFaceRecognizer_create()
        self.mapa_nomes = self._carregar_mapa_nomes()
        self.modelo_carregado = self._carregar_modelo_facial()

        # --- Extras: clima e Arduino ---
        self.cidade_padrao = cidade_padrao
        self.arduino = self._conectar_arduino(porta_arduino)
        self.historico_luz = []  # (hora, valor LDR, nível) para o relatório

        # --- Comandos (padrão Command) ---
        self.comandos = self._construir_comandos()

    # ------------------------------------------------------------------
    # Métodos utilitários de voz
    # ------------------------------------------------------------------
    def falar(self, texto):
        """Converte texto em fala. Usa o edge-tts (voz neural masculina em
        pt-BR) como principal e cai para o pyttsx3 offline se não houver internet."""
        print(f"[Lumi]: {texto}")
        try:
            self._falar_online(texto)
        except Exception as erro:
            print(f"Aviso: falha na síntese de voz online ({erro}). Usando voz offline.")
            self._falar_offline(texto)

    def _falar_online(self, texto):
        """Gera um áudio com edge-tts (voz neural da Microsoft) e toca com o
        pygame. Requer internet."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as arquivo_temp:
            caminho_audio = arquivo_temp.name

        try:
            comunicador = edge_tts.Communicate(texto, voice=self.VOZ_EDGE_TTS)
            asyncio.run(comunicador.save(caminho_audio))
            mixer.music.load(caminho_audio)
            mixer.music.play()
            while mixer.music.get_busy():
                time.sleep(0.1)
            mixer.music.unload()
        finally:
            os.remove(caminho_audio)

    def _falar_offline(self, texto):
        """Plano B sem internet: síntese de voz local via pyttsx3 (SAPI5)."""
        self.motor_voz_offline.say(texto)
        self.motor_voz_offline.runAndWait()

    def ouvir(self, timeout=8, phrase_time_limit=25):
        """Ouve uma frase completa, preservando pausas naturais entre palavras.

        timeout: espera máxima para a pessoa começar a falar.
        phrase_time_limit: duração máxima APÓS o início da fala.
        """
        with sr.Microphone() as microfone:
            # Calibrar em toda tentativa altera o limiar mesmo com alguém falando,
            # podendo tornar o reconhecimento menos confiável. Calibramos uma vez.
            if not self.microfone_calibrado:
                self.falar("Calibrando microfone: fique em silêncio por 2 segundos...")
                self.reconhecedor.adjust_for_ambient_noise(microfone, duration=2)
                self.microfone_calibrado = True
                self.falar("Microfone pronto. Pode falar naturalmente.")
            try:
                audio = self.reconhecedor.listen(microfone, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                return None

        try:
            texto = self.reconhecedor.recognize_google(audio, language="pt-BR")
            return texto.strip().lower()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as erro:
            print(f"Erro ao acessar o serviço de reconhecimento de voz: {erro}")
            return None

    # ------------------------------------------------------------------
    # Ativação e roteamento de comandos (item 1) - padrão Command
    # ------------------------------------------------------------------
    
    def contem_ativacao(self, texto):
        return any(
            re.search(r"\b" + re.escape(palavra) + r"\b", texto)
            for palavra in self.PALAVRAS_ATIVACAO
        )

    def extrair_comando(self, texto):
        comando = texto

        for palavra in sorted(
            self.PALAVRAS_ATIVACAO,
            key=len,
            reverse=True
        ):
            comando = re.sub(
                r"\b" + re.escape(palavra) + r"\b",
                "",
                comando,
                flags=re.IGNORECASE
            )

        return comando.strip(" ,.!?")


    def _construir_comandos(self):
        """Monta a lista de comandos disponíveis (padrão Command): cada item
        associa os gatilhos de fala à ação correspondente. Adicionar um
        comando novo é só incluir uma entrada nova nessa lista."""
        return [
            Comando("cadastrar_evento", self.GATILHOS_CADASTRAR_EVENTO, lambda texto: self.cadastrar_evento()),
            Comando("ler_agenda", self.GATILHOS_LER_AGENDA, lambda texto: self.ler_agenda()),
            Comando("limpar_agenda", self.GATILHOS_LIMPAR_AGENDA, lambda texto: self.limpar_agenda()),
            Comando("hora", self.GATILHOS_HORA, lambda texto: self.falar_hora()),
            Comando("data", self.GATILHOS_DATA, lambda texto: self.falar_data()),
            Comando("calcular", self.GATILHOS_CALCULAR, lambda texto: self.calcular(texto)),
            Comando("reconhecer_face", self.GATILHOS_RECONHECER_FACE, lambda texto: self.reconhecer_face()),
            Comando("cadastrar_rosto", self.GATILHOS_CADASTRAR_FACE, lambda texto: self.cadastrar_rosto()),
            Comando("clima", self.GATILHOS_CLIMA, lambda texto: self.falar_previsao_tempo(texto)),
            Comando("ligar_luz", self.GATILHOS_LIGAR_LUZ, lambda texto: self.controlar_luz("ligar")),
            Comando("desligar_luz", self.GATILHOS_DESLIGAR_LUZ, lambda texto: self.controlar_luz("desligar")),
            Comando("cumprimentar", self.GATILHOS_CUMPRIMENTAR, lambda texto: self.cumprimentar()),
            Comando("verificar_luz", self.GATILHOS_VERIFICAR_LUZ, lambda texto: self.verificar_luz()),
            Comando("relatorio", self.GATILHOS_RELATORIO, lambda texto: self.gerar_relatorio()),
        ]

    def processar_comando(self, comando_texto):
        """Roteia o comando reconhecido: percorre os Comando cadastrados e
        executa o primeiro cujo gatilho bater. Se nenhum bater, cai na IA
        generativa (item 9)."""
        if not comando_texto:
            self.falar("Sim, como posso ajudar?")
            return

        for comando in self.comandos:
            if comando.bate_com(comando_texto):
                comando.executar(comando_texto)
                return

        self.perguntar_ia(comando_texto)

    # ------------------------------------------------------------------
    # Itens 2 e 3: agenda (com dia e horário)
    # ------------------------------------------------------------------
    def cadastrar_evento(self):
        """Pergunta o evento (e tenta extrair dia/horário da mesma resposta);
        se não encontrar, pergunta separadamente. Grava tudo em agenda.txt no
        formato 'evento | data | hora'."""
        self.falar("Ok, qual evento devo cadastrar, e para quando?")
        descricao = self.ouvir(timeout=8, phrase_time_limit=15)

        if not descricao:
            self.falar("Não consegui te ouvir, tente novamente.")
            return

        data_evento = self._extrair_data(descricao)
        hora_evento = self._extrair_hora(descricao)
        nome_evento = self._limpar_nome_evento(descricao)

        if not data_evento:
            self.falar("Para qual dia é esse evento?")
            resposta = self.ouvir(timeout=8, phrase_time_limit=10)
            data_evento = self._extrair_data(resposta or "") or (resposta or "não informado")

        if not hora_evento:
            self.falar("E que horas?")
            resposta = self.ouvir(timeout=8, phrase_time_limit=10)
            hora_evento = self._extrair_hora(resposta or "") or (resposta or "não informado")

        with open(self.arquivo_agenda, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"{nome_evento} | {data_evento} | {hora_evento}\n")

        self.falar(f"Evento {nome_evento} cadastrado para {data_evento} às {hora_evento}.")

    def ler_agenda(self):
        """Lê e fala nome, data e hora de todos os eventos gravados em agenda.txt."""
        if not os.path.exists(self.arquivo_agenda) or os.path.getsize(self.arquivo_agenda) == 0:
            self.falar("Sua agenda está vazia.")
            return

        with open(self.arquivo_agenda, "r", encoding="utf-8") as arquivo:
            linhas = [linha.strip() for linha in arquivo if linha.strip()]

        self.falar(f"Você tem {len(linhas)} evento{'s' if len(linhas) != 1 else ''} cadastrado{'s' if len(linhas) != 1 else ''}.")
        for linha in linhas:
            partes = linha.split(" | ")
            if len(partes) == 3:
                nome, data, hora = partes
                self.falar(f"{nome}, dia {data}, às {hora}.")
            else:
                # compatibilidade com entradas no formato antigo (sem data/hora separadas)
                self.falar(linha)

    def limpar_agenda(self):
        """Remove todos os eventos da agenda, mas mantém o arquivo agenda.txt."""
        try:
            # Abre o arquivo no modo "w", apagando apenas o conteúdo.
            # O arquivo continua existindo.
            with open(self.arquivo_agenda, "w", encoding="utf-8") as arquivo:
                arquivo.truncate(0)

            self.falar("Agenda limpa com sucesso.")

        except Exception as erro:
            # print(f"Erro ao limpar agenda: {erro}")
            self.falar("Não consegui limpar a agenda.")

    def _extrair_data(self, texto):
        """Tenta reconhecer uma data no texto falado (dd/mm[/aaaa], 'dia X de mês',
        'hoje' ou 'amanhã'). Retorna None se não encontrar nada reconhecível."""
        match = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", texto)
        if match:
            dia, mes, ano = match.groups()
            ano = ano or str(datetime.now().year)
            return f"{int(dia):02d}/{int(mes):02d}/{ano}"

        match = re.search(r"dia\s+(\d{1,2})\s+de\s+(\w+)", texto)
        if match:
            dia, mes_nome = match.groups()
            mes_numero = MESES_PT.get(mes_nome.lower())
            if mes_numero:
                return f"{int(dia):02d}/{mes_numero:02d}/{datetime.now().year}"

        if "amanhã" in texto or "amanha" in texto:
            return (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
        if "hoje" in texto:
            return datetime.now().strftime("%d/%m/%Y")

        return None

    def _extrair_hora(self, texto):
        """Tenta reconhecer um horário no texto falado (ex: '14h', '14:30', '14 horas')."""
        match = re.search(r"(\d{1,2})\s*(?:h|horas|:)\s*(\d{2})?", texto)
        if match:
            hora, minuto = match.groups()
            minuto = minuto or "00"
            return f"{int(hora):02d}:{minuto}"
        return None

    def _limpar_nome_evento(self, texto):
        """Remove trechos de data/hora e palavras de conexão do texto falado,
        deixando só a descrição do evento em si."""
        nome = texto
        nome = re.sub(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?", "", nome)
        nome = re.sub(r"dia\s+\d{1,2}\s+de\s+\w+", "", nome)
        nome = re.sub(r"\d{1,2}\s*(?:horas|hora|h|:)\s*\d{0,2}", "", nome)
        nome = re.sub(r"\b(hoje|amanhã|amanha|às|as|para|no|dia)\b", "", nome)
        nome = re.sub(r"\s{2,}", " ", nome).strip(" ,.-")
        return nome or "evento sem nome"

    # ------------------------------------------------------------------
    # Item 4 e 5: hora e data
    # ------------------------------------------------------------------
    def falar_hora(self):
        agora = datetime.now().strftime("%H:%M")
        self.falar(f"Agora são {agora}.")

    def falar_data(self):
        hoje = datetime.now().strftime("%d de %B de %Y")
        self.falar(f"Hoje é {hoje}.")

    # ------------------------------------------------------------------
    # Item 6: calculadora por voz
    # ------------------------------------------------------------------
    def calcular(self, comando):
        """Extrai dois números e um operador do comando falado e resolve a conta."""
        numeros = re.findall(r"-?\d+(?:[.,]\d+)?", comando)
        numeros = [float(numero.replace(",", ".")) for numero in numeros]

        operador_encontrado = None
        for operador in sorted(self.OPERADORES, key=len, reverse=True):
            if operador in comando:
                operador_encontrado = operador
                break

        if len(numeros) < 2 or operador_encontrado is None:
            self.falar("Não consegui entender a conta. Tente algo como: calcular dois mais dois.")
            return

        try:
            resultado = self.OPERADORES[operador_encontrado](numeros[0], numeros[1])
            self.falar(f"O resultado é {resultado}.")
        except ZeroDivisionError:
            self.falar("Não é possível dividir por zero.")

    # ------------------------------------------------------------------
    # Item 7: reconhecimento facial (sem abrir janela de câmera)
    # ------------------------------------------------------------------
    def _carregar_mapa_nomes(self):
        """Carrega o mapa rótulo numérico -> nome, gerado por treinar_modelo.py."""
        mapa = {0: "desconhecido"}
        caminho = os.path.join("rostos", "mapa_nomes.txt")
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as arquivo:
                for linha in arquivo:
                    rotulo, nome = linha.strip().split(",", 1)
                    mapa[int(rotulo)] = nome
        return mapa

    def _carregar_modelo_facial(self):
        """Carrega o modelo .yml pré-treinado, se ele existir."""
        if os.path.exists(self.modelo_facial):
            self.reconhecedor_facial.read(self.modelo_facial)
            return True
        print("Aviso: modelo facial não encontrado. Rode capturar_rosto.py e treinar_modelo.py antes de usar 'reconhecer face'.")
        return False

    def reconhecer_face(self):
        """Abre a webcam (sem exibir nenhuma janela) e tenta identificar a
        pessoa em frente à câmera, combinando várias leituras seguidas
        (votação) para reduzir erros de uma leitura isolada. Se a maioria
        das leituras não bater com ninguém cadastrado, a pessoa é
        considerada 'desconhecida'."""
        if not self.modelo_carregado:
            self.falar("Ainda não tenho um modelo treinado para reconhecer rostos.")
            return

        self.falar("Deixa eu dar uma olhada...")
        camera = cv2.VideoCapture(0, BACKEND_CAMERA)
        votos = []
        tentativas = 0
        limite_tentativas = 90  # tempo máximo esperando um rosto aparecer
        total_leituras_desejado = 15  # quantas leituras usar pra decidir por votação

        try:
            while tentativas < limite_tentativas and len(votos) < total_leituras_desejado:
                ok, frame = camera.read()
                if not ok:
                    break

                cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.classificador_face.detectMultiScale(cinza, scaleFactor=1.2, minSize=(150, 150))

                for (x, y, largura, altura) in faces:
                    rosto = cv2.resize(cinza[y:y + altura, x:x + largura], (220, 220))
                    rotulo, confianca = self.reconhecedor_facial.predict(rosto)
                    # confiança alta = pouco parecido -> trata como desconhecido
                    nome = self.mapa_nomes.get(rotulo, "desconhecido") if confianca <= self.LIMITE_CONFIANCA_FACE else "desconhecido"
                    votos.append(nome)
                    break

                tentativas += 1
        finally:
            camera.release()

        if not votos:
            self.falar("Não consegui ver nenhum rosto.")
            return

        nome_mais_votado = max(set(votos), key=votos.count)
        if nome_mais_votado != "desconhecido":
            self.falar(f"Você é {nome_mais_votado}!")
        else:
            self.falar("Rosto não reconhecido. Você consta como desconhecido.")

    def cadastrar_rosto(self):
        """Pergunta o nome por voz e captura as amostras de rosto
        automaticamente (sem precisar de tecla ou janela de câmera),
        narrando o progresso, e depois treina o modelo com o novo rosto."""
        self.falar("Qual o nome da pessoa que eu devo cadastrar?")
        nome = self.ouvir(timeout=8, phrase_time_limit=8)

        if not nome:
            self.falar("Não consegui te ouvir, tente novamente.")
            return

        nome = nome.replace(" ", "")  # evita espaços no nome do arquivo de amostra
        self.falar(
            f"Ok, vamos capturar o rosto de {nome}. Olhe para a câmera, mantenha o rosto "
            "enquadrado fique com a cabeça parada. Começando "
            "capturadas"
        )

        try:
            capturar_rosto.capturar_amostras(
                nome,
                callback_progresso=self._narrar_progresso_captura,
                mostrar_janela=False,
            )
        except Exception as erro:
            print(f"Erro durante a captura de rosto: {erro}")
            self.falar("Houve um problema durante a captura das amostras.")
            return

        self.falar(f"Captura concluída. Adicionando rosto de {nome} a memória.")

        resultado_treino = subprocess.run([sys.executable, "treinar_modelo.py"])
        if resultado_treino.returncode != 0:
            self.falar("Houve um problema ao adicionar rosto.")
            return

        # recarrega o modelo e o mapa de nomes em memória, sem precisar reiniciar o assistente
        self.mapa_nomes = self._carregar_mapa_nomes()
        self.modelo_carregado = self._carregar_modelo_facial()
        self.falar(f"{nome} cadastrado e modelo atualizado com sucesso.")

    def _narrar_progresso_captura(self, amostra_atual, total_amostras):
        """Callback chamado a cada foto salva por capturar_rosto.py, usado
        pra narrar o andamento da captura por voz em alguns marcos."""
        print(f"Amostra {amostra_atual}/{total_amostras} salva.")
        if amostra_atual == 1:
            self.falar("Começando a captura.")
        elif amostra_atual == total_amostras // 2:
            self.falar("Metade das capturadas. Continue.")
        elif amostra_atual == total_amostras:
            self.falar("Capturadas encerradas.")

    # ------------------------------------------------------------------
    # Item 9: IA generativa (Groq) - fallback para perguntas abertas
    # ------------------------------------------------------------------
    def _perguntar_groq(self, pergunta, sistema=None):
        """Consulta a Groq e devolve o texto da resposta (levanta exceção se falhar)."""
        resposta = self.groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": sistema or (
                        "Você é o LumiBot, um robô assistente objetivo. "
                        "Responda sempre em português, em no máximo 40 palavras."
                    ),
                },
                {"role": "user", "content": pergunta},
            ],
        )
        return resposta.choices[0].message.content

    def perguntar_ia(self, comando):
        self.falar("Deixa eu pensar...")
        try:
            self.falar(self._perguntar_groq(comando))
        except Exception as erro:
            print(f"Erro ao consultar a IA generativa: {erro}")
            self.falar("Não consegui pensar em uma resposta agora.")

    # ------------------------------------------------------------------
    # Item 10 (extra 1): previsão do tempo
    # ------------------------------------------------------------------
    def falar_previsao_tempo(self, comando):
        """Consulta o clima atual (wttr.in, sem necessidade de API key)."""
        match = re.search(r"em (.+)", comando)
        cidade = match.group(1).strip() if match else self.cidade_padrao

        try:
            resposta = requests.get(f"https://wttr.in/{cidade}?format=j1", timeout=6)
            dados = resposta.json()
            condicao_atual = dados["current_condition"][0]
            temperatura = condicao_atual["temp_C"]
            descricao = (
                condicao_atual["lang_pt"][0]["value"]
                if "lang_pt" in condicao_atual
                else condicao_atual["weatherDesc"][0]["value"]
            )
            self.falar(f"Em {cidade} agora está {temperatura} graus, com {descricao}.")
        except Exception as erro:
            print(f"Erro ao consultar previsão do tempo: {erro}")
            self.falar("Não consegui consultar a previsão do tempo agora.")

    # ------------------------------------------------------------------
    # Item 10 (extra 2): controle de dispositivo via Arduino
    # ------------------------------------------------------------------
    def _conectar_arduino(self, porta):
        """Conecta ao Arduino na porta informada ou, se porta=None, procura
        sozinho. Falha graciosamente se não houver hardware."""
        if serial is None:
            return None
        if not porta:
            for p in serial.tools.list_ports.comports():
                if any(k in (p.description or "") for k in ("Arduino", "CH340", "USB-SERIAL")) \
                        or "ACM" in p.device or "usbmodem" in p.device:
                    porta = p.device
                    break
        if not porta:
            print("Aviso: Arduino não encontrado. Comandos do robô ficarão indisponíveis.")
            return None
        try:
            conexao = serial.Serial(porta, 9600, timeout=5)
            time.sleep(2)  # aguarda o Arduino reiniciar após abrir a porta
            print(f"Arduino conectado em {porta}.")
            return conexao
        except Exception as erro:
            print(f"Aviso: não foi possível conectar ao Arduino ({erro}). Comandos do robô ficarão indisponíveis.")
            return None

    def _enviar_arduino(self, comando, aguardar=True):
        """Envia um comando (uma linha) ao Arduino e devolve a resposta."""
        if not self.arduino:
            raise ConnectionError("Arduino não conectado")
        self.arduino.reset_input_buffer()
        self.arduino.write((comando + "\n").encode())
        self.arduino.flush()
        if aguardar:
            return self.arduino.readline().decode(errors="ignore").strip()
        return ""

    def controlar_luz(self, comando):
        if not self.arduino:
            self.falar("Não encontrei nenhum Arduino conectado.")
            return
        if comando == "ligar":
            self._enviar_arduino("E:1")
            self._enviar_arduino("D:1")
            self.falar("Luz ligada.")
        else:
            self._enviar_arduino("E:0")
            self._enviar_arduino("D:0")
            self.falar("Luz desligada.")

    # ------------------------------------------------------------------
    # Robô CitizenTech: cumprimento, monitoramento de iluminação e relatório
    # ------------------------------------------------------------------
    def cumprimentar(self):
        """LED verde + servo acena enquanto o robô fala."""
        if self.arduino:
            self._enviar_arduino("OI", aguardar=False)
        self.falar("Olá! Sou o Lumi, o robô de monitoramento de iluminação. Como posso ajudar?")
        if self.arduino:
            resposta = self.arduino.readline().decode(errors="ignore").strip()
            if resposta != "OK":
                print(f"Aviso: resposta inesperada ao cumprimento: {resposta!r}")

    def _classificar_luz(self, valor):
        if valor > self.LIMIAR_ESCURO:
            return "insuficiente"
        if valor > self.LIMIAR_PENUMBRA:
            return "baixa"
        return "adequada"

    def verificar_luz(self):
        """Servo varre a área, o LDR é lido, o LED vermelho avisa se a
        iluminação for insuficiente e a Groq explica a situação por voz."""
        if not self.arduino:
            self.falar("Não encontrei nenhum Arduino conectado.")
            return

        self.falar("Verificando a iluminação do local.")
        self._enviar_arduino("VARRER")
        try:
            valor = int(self._enviar_arduino("LER").split(":")[1])
        except (IndexError, ValueError, AttributeError, ConnectionError):
            self.falar("Não consegui ler o sensor de luz.")
            return

        nivel = self._classificar_luz(valor)
        self.historico_luz.append((datetime.now().strftime("%H:%M:%S"), valor, nivel))
        self._enviar_arduino("ALERTA:1" if nivel == "insuficiente" else "ALERTA:0")

        try:
            self.falar(self._perguntar_groq(
                f"Leitura do sensor LDR: {valor}. Iluminação {nivel}. "
                "Explique a situação para quem está no local e diga se é preciso acionar a manutenção. Explique que quando menor o valor do LDR, mais claro é o ambiente, valores próximos de 1000 indicam ambiente mais escuro. Lembre ao usuário que ele pode pedir um relatório de manutenção.",
                sistema=(
                    "Você é o LumiBot, robô de monitoramento de iluminação em espaços "
                    "públicos (projeto CitizenTech). Responda em português, em no máximo 40 palavras, "
                    "sem markdown."
                ),
            ))
        except Exception as erro:
            print(f"Erro ao consultar a IA generativa: {erro}")
            self.falar(f"A iluminação está {nivel}.")

    def gerar_relatorio(self):
        """Pede à Groq um relatório de manutenção com as leituras feitas e salva em relatorio.txt."""
        if not self.historico_luz:
            self.falar("Ainda não tenho leituras. Peça para eu verificar a iluminação primeiro.")
            return

        linhas = "\n".join(f"{h} - LDR {v} ({n})" for h, v, n in self.historico_luz)
        try:
            texto = self._perguntar_groq(
                "Gere um relatório curto de manutenção da iluminação pública com base nestas leituras:\n" + linhas,
                sistema=(
                    "Você é um robô de monitoramento de iluminação pública (projeto CitizenTech). "
                    "Responda em português, em no máximo 60 palavras, sem markdown."
                ),
            )
        except Exception as erro:
            print(f"Erro ao consultar a IA generativa: {erro}")
            texto = "Não consegui gerar o resumo, mas as leituras foram registradas."

        with open("relatorio.txt", "w", encoding="utf-8") as arquivo:
            arquivo.write(f"Relatório gerado em {datetime.now():%d/%m/%Y %H:%M}\n\n{linhas}\n\n{texto}\n")
        self.falar(texto)

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------
    def executar(self):
        """Loop de escuta contínua: só age quando ouve a palavra de ativação."""
        self.cumprimentar()
        while True:
            texto = self.ouvir()
            if not texto:
                continue

            # Requisito 1: qualquer fala reconhecida é impressa na tela
            print(f"[Reconhecido]: {texto}")

            if self.contem_ativacao(texto):
                comando = self.extrair_comando(texto)
                # Permite dizer primeiro "Lumi" e, após a resposta, completar
                # a frase sem repetir o nome do robô.
                if not comando:
                    self.falar("Estou ouvindo. Pode falar seu comando.")
                    comando = self.ouvir(timeout=10, phrase_time_limit=25)
                    if not comando:
                        self.falar("Não consegui ouvir o comando inteiro. Tente novamente.")
                        continue
                    print(f"[Comando]: {comando}")
                self.processar_comando(comando)
            # sem a palavra de ativação, nenhuma ação é executada


if __name__ == "__main__":
    def carregar_chave_groq(caminho="api_AI.txt"):
        """Lê a chave da API da Groq de um arquivo de texto simples (1 linha, só a chave)."""
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                return arquivo.read().strip()
        except FileNotFoundError:
            print(f"Aviso: arquivo '{caminho}' não encontrado. Crie esse arquivo com sua chave da Groq dentro.")
            return None

    # Porta do Arduino -- ex: "COM3" no Windows ou "/dev/ttyUSB0" no Linux.
    # Com None, o assistente procura o Arduino sozinho.
    assistente = AssistenteVirtual(
        groq_api_key=carregar_chave_groq(),
        porta_arduino=None,
        cidade_padrao="Santo André",
    )
    assistente.executar()
