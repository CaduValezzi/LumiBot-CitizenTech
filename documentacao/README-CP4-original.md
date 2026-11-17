# LumiBot — Assistente Virtual por Voz

Projeto acadêmico de assistente virtual por voz, inspirado no Google Assistente e na Alexa. Reconhece comandos de voz em português, responde por síntese de voz, reconhece rostos via webcam e integra com uma IA generativa (Groq) para perguntas abertas.

## Funcionalidades

| # | Comando de voz (aceita variações) | O que faz |
|---|---|---|
| 1 | `"Lumi"` / `"LumiBot"` | Palavra de ativação. Sem ela, nenhum comando é executado — o texto ouvido é só exibido no console. |
| 2 | "cadastrar evento", "novo evento", "criar evento"... | Pergunta o evento, escuta a resposta e grava em `agenda.txt`. |
| 3 | "ler agenda", "mostrar agenda", "quais são meus eventos"... | Lê em voz alta todos os eventos cadastrados. |
| 4 | "que horas são", "me diz as horas"... | Fala o horário atual. |
| 5 | "que dia é hoje", "qual a data de hoje"... | Fala a data atual. |
| 6 | `"calcular ..."` | Resolve contas de adição, subtração, multiplicação e divisão. |
| 7 | "reconhecer face", "quem sou eu"... | Abre a webcam e tenta identificar a pessoa. |
| 8 | "limpar agenda", "zerar agenda"... | Apaga o conteúdo de `agenda.txt` sem excluir o arquivo. |
| 9 | Qualquer pergunta aberta | Cai como *fallback* para a IA generativa (Groq). |
| 10 | "qual o clima", "vai chover"... / "ligar luz" / "desligar luz" | Extras: previsão do tempo e controle de um LED via Arduino. |
| Bônus | "cadastrar rosto", "novo rosto"... | Pergunta o nome por voz, roda a captura de amostras e retreina o modelo facial, sem sair do assistente. |

Todos os gatilhos aceitos por comando estão centralizados nas constantes `GATILHOS_*` no topo da classe `AssistenteVirtual`, em `assistente.py` — dá pra adicionar mais variações de fala editando essas listas.

## Estrutura do projeto

```
assistente-Lumi/
├── assistente.py            # classe AssistenteVirtual + loop principal
├── capturar_rosto.py         # captura amostras de rosto (chamado direto ou pelo assistente)
├── treinar_modelo.py         # treina o EigenFaceRecognizer e salva o modelo
├── requirements.txt
├── api_AI.txt                 # sua chave da Groq (não vai pro Git)
├── agenda.txt                 # criado automaticamente no primeiro uso
├── classificador_eigen.yml    # gerado por treinar_modelo.py
└── rostos/
    ├── fotos/                  # amostras capturadas por pessoa
    └── mapa_nomes.txt           # gerado por treinar_modelo.py
```

## Requisitos

- **Python 3.12** (recomendado). O PyAudio só tem wheels pré-compiladas para Windows até o Python 3.13; em versões mais novas (3.14+) a instalação tende a falhar por falta de wheel pronta.

## Instalação

1. Clone o repositório e entre na pasta:
   ```bash
   git clone <url-do-seu-repositorio>
   cd assistente-Lumi
   ```

2. Se não tiver o Python 3.12 instalado, no Windows dá pra instalar direto pelo terminal:
   ```bash
   winget install Python.Python.3.12
   ```

3. Crie o ambiente virtual usando essa versão:
   ```bash
   py -3.12 -m venv venv
   venv\Scripts\activate   # Linux/macOS: source venv/bin/activate
   ```

4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

   > No Windows, se `pip install pyaudio` falhar, instale o pacote pré-compilado com
   > `pip install pipwin && pipwin install pyaudio`, ou baixe o wheel correspondente.

   > **Atenção:** o `requirements.txt` já fixa `opencv-contrib-python==4.13.0.92` de propósito.
   > A versão 5.0.0.93 (mais recente) tem um [bug conhecido](https://github.com/opencv/opencv-python/issues/1244)
   > que faz a pasta `cv2/data` vir vazia, quebrando o reconhecimento facial (sem os arquivos `haarcascade_*.xml`).

5. Configure sua chave da API da Groq (gratuita em [console.groq.com](https://console.groq.com)) criando um arquivo `api_AI.txt` na raiz do projeto, com **apenas a chave** dentro, sem espaços ou aspas:
   ```
   gsk_sua_chave_aqui
   ```
   Esse arquivo já está no `.gitignore`, então não vai parar no seu repositório público.

## Como treinar o reconhecimento facial (item 7)

Duas formas de fazer isso:

**Pelo assistente (recomendado):** com o `assistente.py` rodando, diga *"Lumi cadastrar rosto"*. Ele pergunta o nome por voz e começa a captura automaticamente — não abre nenhuma janela de câmera nem precisa apertar tecla, basta manter o rosto enquadrado e virar levemente a cabeça pros lados. O próprio assistente narra o andamento ("começando a captura", "metade das fotos capturadas"...) e, ao terminar as 25 fotos, treina o modelo na sequência sozinho, recarregando tudo sem precisar reiniciar.

**Manualmente, rodando os scripts direto:**
1. `python capturar_rosto.py` (pergunta o nome no terminal) ou `python capturar_rosto.py nome_da_pessoa` (pula a pergunta). Nesse modo, abre uma janela com o vídeo pra você se enquadrar; a captura em si continua automática — sem precisar apertar tecla nenhuma, exceto `q` se quiser cancelar antes de terminar.
2. Capture também amostras de rostos aleatórios com o nome `desconhecido`, para o modelo aprender a rejeitar quem não está cadastrado.
3. `python treinar_modelo.py` — gera `classificador_eigen.yml` e `rostos/mapa_nomes.txt`.

## Como executar

```bash
python assistente.py
```

A assistente vai falar "LumiBot ativado" e ficar ouvindo o microfone. Diga o nome de ativação seguido do comando, por exemplo: *"Lumi, que horas são"*.

### Controle do Arduino (extra)

Para usar os comandos de luz, informe a porta serial ao instanciar a classe em `assistente.py`:

```python
assistente = AssistenteVirtual(porta_arduino="COM3")  # ou "/dev/ttyUSB0" no Linux
```

O Arduino deve estar programado para ligar/desligar um LED ao receber os bytes `b"a"` (ligar) e `b"b"` (desligar) pela porta serial.

## Dependências principais

- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) + PyAudio — captura e transcrição de voz
- [edge-tts](https://pypi.org/project/edge-tts/) + [pygame](https://pypi.org/project/pygame/) — síntese de voz principal (voz neural masculina em pt-BR, via Microsoft Edge, gratuita e sem chave de API)
- [pyttsx3](https://pypi.org/project/pyttsx3/) — síntese de voz offline, usada só como plano B se não houver internet
- [opencv-contrib-python](https://pypi.org/project/opencv-contrib-python/) (fixado em `4.13.0.92`) — detecção e reconhecimento facial
- [groq](https://pypi.org/project/groq/) — IA generativa
- [requests](https://pypi.org/project/requests/) — consulta de previsão do tempo (wttr.in)
- [pyserial](https://pypi.org/project/pyserial/) — comunicação com Arduino

## Notas técnicas

- No Windows, a webcam é aberta com o backend DirectShow (`cv2.CAP_DSHOW`) em vez do padrão MSMF, que é bem mais lento pra inicializar. Em Linux/macOS isso é detectado automaticamente e ignorado.
- A voz principal (edge-tts) precisa de internet — o mesmo vale pro reconhecimento de voz (Google) e pra IA generativa (Groq), então isso não é uma dependência nova pro projeto.
- Pra trocar a voz, edite a constante `VOZ_EDGE_TTS` no topo da classe `AssistenteVirtual`. Masculina: `"pt-BR-AntonioNeural"` (padrão); feminina: `"pt-BR-FranciscaNeural"`. Rode `edge-tts --list-voices | findstr pt-BR` (Windows) para ver todas as opções em português.
- O reconhecimento facial (`reconhecer_face`) combina até 15 leituras seguidas da câmera e decide por votação (a resposta mais frequente entre elas), em vez de confiar numa única leitura isolada. Rostos não cadastrados — ou com confiança abaixo do limiar definido em `LIMITE_CONFIANCA_FACE` — são sempre classificados como "desconhecido".

## Autor

Cadu — projeto acadêmico.