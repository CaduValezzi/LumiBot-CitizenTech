# LumiBot — CitizenTech

Protótipo acadêmico de monitoramento de iluminação em espaços públicos. Um **Arduino Uno** lê um sensor LDR, move a cabeça do robô com servo SG90 e controla três LEDs. Um **notebook** executa o assistente Python do CP4, que reconhece voz, consulta uma LLM pela Groq e responde por voz sintetizada. O corpo fixo é feito de papelão.

> **Estado:** integração de software preparada; montagem física e calibração ainda precisam de testes. As leituras são indicativas, não substituem um luxímetro para avaliação técnica de iluminação pública.

## Materiais e conexões

| Peça | Arduino Uno |
|---|---|
| LDR (saída analógica em divisor de tensão) | A0 |
| LED olho direito + resistor de 330 Ω | D6 |
| LED olho esquerdo + resistor de 330 Ω | D8 |
| LED alerta + resistor de 330 Ω | D7 |
| Servo SG90, fio de sinal | D9 |
| GND dos componentes | GND comum |

- Arduino Uno: alimentação e comunicação via USB do notebook, sem tomada.
- Servo: alimentação externa por **power bank USB de 5 V** com capacidade de corrente suficiente; conectar o negativo da alimentação do servo ao GND do Arduino. **Não interligar os positivos 5 V do power bank e do Arduino.**
- Cada LED precisa de resistor **em série** e retorno ao GND.
- Para um **LDR avulso**, usar divisor de tensão (por exemplo, resistor de 10 kΩ); ligar o ponto central ao A0. Para um módulo, conferir se a saída é analógica `AO` e compatível com a tensão do Arduino Uno.
- Nunca alimentar o servo pelo pino digital D9: esse pino é apenas sinal.

### Estrutura de papelão

- Base: 18 × 18 cm.
- Corpo: 10 cm de largura × 8 cm de profundidade × **18 cm de altura**.
- Cabeça leve: 10 × 10 × 10 cm; dois olhos de LED e LDR exposto à luz.
- Servo fixado no topo do corpo, com eixo vertical; braço do servo preso ao fundo reforçado da cabeça.
- Instalar o Arduino e os fios no corpo, com abertura traseira para USB e acesso para manutenção.

## Instalação

1. Na **Arduino IDE**, selecionar **Arduino Uno** e a porta correta. Abrir `arduino/LumeBot/LumeBot.ino` e enviar para a placa (biblioteca `Servo` padrão).
2. Em Windows, instalar **Python 3.12**. No terminal, na raiz do repositório:

   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configurar a chave da Groq em `python/api_AI.txt` (uma linha contendo a chave; arquivo ignorado pelo Git). **Nunca enviar chaves para o GitHub**.
4. Conectar Arduino por USB e fechar o Monitor Serial antes de iniciar o Python. Na pasta `python`, executar:

   ```powershell
   cd python
   python assistente.py
   ```

5. O assistente tenta detectar a porta automaticamente. Se necessário, definir `porta_arduino="COM3"` na instanciação ao final de `assistente.py`, substituindo pela porta real.

**Internet necessária** para reconhecimento de voz do Google, voz neural `edge-tts` e LLM Groq. O `pyttsx3` fornece alternativa offline somente para a voz sintetizada. O reconhecimento facial é opcional e exige dados/treinamento local; o modelo biométrico não acompanha o repositório público.

## Comandos de voz para demonstração

Inicie com a palavra **“Lumi”** junto do comando ou diga apenas “Lumi” e aguarde a resposta antes de falar o comando:

| Frase | Resultado |
|---|---|
| “Lumi, olá” | Cumprimento falado, LEDs e movimento da cabeça |
| “Lumi, verificar iluminação” | Servo varre, Arduino envia leitura LDR, Python classifica e LLM explica por voz |
| “Lumi, ligar luz” | Acende os dois LEDs dos olhos e ativa alerta |
| “Lumi, desligar luz” | Apaga LEDs e alerta |
| “Lumi, relatório” | Gera `python/relatorio.txt` com leituras e síntese por LLM |

O comando de voz é reconhecido no notebook. O Python envia texto pela serial USB (9600 baud) para o Arduino, que executa a ação e responde. **A classificação de iluminação é atualmente por limiares calibráveis**; a **LLM é usada para gerar as orientações e o relatório**. Não há modelo TinyML treinado embarcado.

### Todos os gatilhos aceitos

Os gatilhos abaixo estão definidos em [`python/assistente.py`](python/assistente.py). Use uma palavra de ativação (`lumi`, `lumibote`, `lume` ou `lumebote`) junto do comando, por exemplo: “Lumi, ler agenda”. Também é possível dizer apenas “Lumi”, aguardar a resposta e então falar o comando.

| Comando | Gatilhos de voz |
|---|---|
| Cadastrar evento | `cadastrar evento`, `cadastra um evento`, `cadastra evento`, `novo evento`, `criar evento` |
| Ler agenda | `ler agenda`, `leia a agenda`, `ler minha agenda`, `mostrar agenda`, `quais são meus eventos` |
| Limpar agenda | `limpar agenda`, `apagar a agenda`, `apagar agenda`, `limpar minha agenda`, `zerar agenda` |
| Consultar hora | `que horas são`, `que horas é`, `me diz as horas`, `qual é a hora`, `que horas` |
| Consultar data | `que dia é hoje`, `que dia é`, `qual o dia de hoje`, `qual a data de hoje`, `que dia` |
| Calcular | `calcular` |
| Reconhecer face | `reconhecer face`, `quem sou eu`, `reconheça minha face`, `reconhece minha face` |
| Cadastrar rosto | `cadastrar rosto`, `cadastra um rosto`, `cadastra rosto`, `novo rosto`, `criar rosto` |
| Consultar clima | `clima`, `previsão do tempo`, `previsao do tempo`, `qual o clima`, `vai chover` |
| Ligar luz | `ligar luz`, `acender luz`, `acende a luz` |
| Desligar luz | `desligar luz`, `apagar luz`, `apaga a luz` |
| Cumprimentar | `olá`, `bom dia`, `boa tarde`, `boa noite`, `tudo bem` |
| Verificar iluminação | `como está a luz`, `como está a iluminação`, `verificar iluminação`, `verificar a iluminação`, `verificar luz`, `analisar iluminação`, `iluminação` |
| Gerar relatório | `relatório`, `relatorio` |

A calculadora aceita `multiplicado por`, `dividido por`, `mais`, `menos`, `vezes`, `+`, `-`, `x`, `/` e `elevado`. Exemplo: “Lumi, calcular 2 mais 3”. Para consultar outra cidade, diga “Lumi, clima em São Paulo”. Para gerar um relatório, faça primeiro uma verificação de iluminação.

Os gatilhos são procurados como trechos do texto reconhecido, e o primeiro comando correspondente na ordem da tabela é executado. Se nenhum gatilho corresponder, a pergunta é enviada à IA generativa (Groq).

## Protocolo serial

| Comando | Resposta | Ação |
|---|---|---|
| `OI` | `OK` | Pisca olhos e movimenta cabeça |
| `VARRER` | `OK` | Giro de inspeção |
| `LER` | `LDR:<valor>` | Média de dez leituras de A0 |
| `LUZ` | `LDR:<valor>` e `NIVEL:<nivel>` | Teste completo na própria placa |
| `ALERTA:1` / `ALERTA:0` | `OK` | Ativa/desativa LED de alerta |
| `E:1` / `E:0`, `D:1` / `D:0` | `OK` | Controle independente dos olhos |

**Calibração obrigatória:** abrir Monitor Serial a 9600 baud e enviar `LER` com o LDR sob luz forte e pouca luz. Comparar a direção da leitura; depois ajustar `LIMIAR_ESCURO` e `LIMIAR_PENUMBRA` em `python/assistente.py` e `arduino/LumeBot/LumeBot.ino`. O código inicial assume que **valores maiores indicam menos luz**, o que depende do divisor de tensão utilizado. Não declarar as classificações confiáveis sem esse teste.

## Verificação antes da gravação

1. Verificar GND comum e isolação do positivo da bateria.
2. Testar `OI`, `LER`, `VARRER`, `ALERTA:1`, `ALERTA:0`, `VERDE:1`, `VERDE:0` no Monitor Serial.
3. Fechar o Monitor Serial, iniciar o Python e testar voz + movimento + LEDs.
4. Variar a iluminação e conferir leitura, classificação e explicação falada.
5. Gravar vídeo com até 6 minutos mostrando cenário CitizenTech, circuito, leitura real e resposta contextualizada.

## Arquivos

- `python/assistente.py`: CP4 preservado com pequenas correções de comunicação.
- `python/capturar_rosto.py` e `python/treinar_modelo.py`: extras opcionais do CP4.
- `arduino/LumeBot/LumeBot.ino`: firmware atualizado do Uno.
- `documentacao/README-CP4-original.md`: documentação anterior para referência.
- `requirements.txt`: bibliotecas Python.
