"""
Script auxiliar para capturar amostras de rosto usadas no treinamento do
reconhecimento facial (item 7 do assistente).

Rode este script uma vez para cada pessoa que a assistente deve reconhecer.
DICA do professor: rode também pelo menos uma vez com o nome "desconhecido",
usando fotos de outras pessoas/ângulos, para melhorar a precisão do modelo.

A captura é automática: nenhuma tecla precisa ser pressionada. Basta manter
o rosto enquadrado que as fotos são salvas sozinhas, em intervalos de tempo,
até completar o total de amostras.

Uso:
    python capturar_rosto.py                 # pergunta o nome no terminal
    python capturar_rosto.py joao             # usa "joao" sem perguntar
                                               # (usado pelo assistente.py, que já
                                               #  coleta o nome por voz antes de chamar)
"""

import argparse
import os
import sys
import time

import cv2

PASTA_FOTOS = os.path.join("rostos", "fotos")
NUMERO_MAX_AMOSTRAS = 25
TAMANHO_AMOSTRA = (220, 220)
INTERVALO_ENTRE_FOTOS_SEGUNDOS = 0.4  # evita salvar várias fotos praticamente iguais

# No Windows, o backend padrão (MSMF) demora vários segundos pra abrir a
# câmera; o DirectShow abre quase instantâneo. Em Linux/macOS mantemos o
# backend automático, já que CAP_DSHOW só existe no Windows.
BACKEND_CAMERA = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY


def capturar_amostras(nome, callback_progresso=None, mostrar_janela=False):
    """Captura NUMERO_MAX_AMOSTRAS fotos do rosto da pessoa informada, de
    forma automática (sem precisar pressionar nenhuma tecla).

    callback_progresso(amostra_atual, total): se informado, é chamado a cada
    foto salva -- usado pelo assistente.py pra narrar o progresso por voz.
    Se omitido, o progresso é apenas impresso no console.

    mostrar_janela: se True, abre uma janela cv2 mostrando o vídeo (útil ao
    rodar o script sozinho pelo terminal). O assistente chama com False, pra
    não abrir nenhuma aba de câmera.
    """
    os.makedirs(PASTA_FOTOS, exist_ok=True)
    classificador = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    camera = cv2.VideoCapture(0, BACKEND_CAMERA)

    amostra = 1
    momento_ultima_foto = 0.0

    try:
        while amostra <= NUMERO_MAX_AMOSTRAS:
            ok, imagem = camera.read()
            if not ok:
                break

            cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
            faces = classificador.detectMultiScale(cinza, scaleFactor=1.05, minSize=(150, 150))

            agora = time.time()
            if len(faces) > 0 and (agora - momento_ultima_foto) >= INTERVALO_ENTRE_FOTOS_SEGUNDOS:
                x, y, largura, altura = faces[0]
                rosto = cv2.resize(cinza[y:y + altura, x:x + largura], TAMANHO_AMOSTRA)
                caminho = os.path.join(PASTA_FOTOS, f"{nome}_{amostra}.jpg")
                cv2.imwrite(caminho, rosto)
                momento_ultima_foto = agora

                if callback_progresso:
                    callback_progresso(amostra, NUMERO_MAX_AMOSTRAS)
                else:
                    print(f"Amostra {amostra}/{NUMERO_MAX_AMOSTRAS} salva.")

                amostra += 1

            if mostrar_janela:
                for (x, y, largura, altura) in faces:
                    cv2.rectangle(imagem, (x, y), (x + largura, y + altura), (0, 0, 255), 2)
                cv2.imshow("Captura de rosto (pressione Q para cancelar)", imagem)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        camera.release()
        if mostrar_janela:
            cv2.destroyAllWindows()

    print(f"Captura de '{nome}' concluída.")


def obter_nome_pessoa():
    """Lê o nome via argumento de linha de comando (se informado) ou pergunta no terminal."""
    parser = argparse.ArgumentParser(description="Captura amostras de rosto para o treinamento.")
    parser.add_argument(
        "nome",
        nargs="?",
        default=None,
        help="Nome da pessoa (ou 'desconhecido'). Se omitido, o script pergunta no terminal.",
    )
    argumentos = parser.parse_args()

    if argumentos.nome:
        return argumentos.nome.strip()
    return input("Digite o nome da pessoa (ou 'desconhecido' para amostras negativas): ").strip()


if __name__ == "__main__":
    # Ao rodar o script sozinho pelo terminal, mostramos a janela da câmera
    # (mostrar_janela=True) pra você poder se enquadrar. O assistente.py, ao
    # chamar capturar_amostras() diretamente, usa mostrar_janela=False.
    nome_pessoa = obter_nome_pessoa()
    print("Olhe para a câmera. As fotos são capturadas automaticamente enquanto seu rosto for detectado.")
    capturar_amostras(nome_pessoa, mostrar_janela=True)