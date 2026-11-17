"""
Treina o modelo EigenFaceRecognizer com as amostras capturadas por
capturar_rosto.py e gera dois arquivos usados pelo assistente:
 - classificador_eigen.yml  -> o modelo treinado em si
 - rostos/mapa_nomes.txt    -> mapeamento entre rótulo numérico e nome

Uso:
    python treinar_modelo.py
"""

import os

import cv2
import numpy as np

PASTA_FOTOS = os.path.join("rostos", "fotos")
ARQUIVO_MODELO = "classificador_eigen.yml"
ARQUIVO_MAPA = os.path.join("rostos", "mapa_nomes.txt")
TAMANHO_AMOSTRA = (220, 220)


def montar_dataset():
    """Lê todas as fotos da pasta e monta as listas de imagens e rótulos numéricos."""
    caminhos = [os.path.join(PASTA_FOTOS, arquivo) for arquivo in os.listdir(PASTA_FOTOS)]
    faces = []
    rotulos = []
    mapa_nome_para_rotulo = {"desconhecido": 0}
    proximo_rotulo = 1

    for caminho in caminhos:
        nome = os.path.basename(caminho).split("_")[0]
        if nome not in mapa_nome_para_rotulo:
            mapa_nome_para_rotulo[nome] = proximo_rotulo
            proximo_rotulo += 1

        imagem = cv2.imread(caminho, cv2.IMREAD_GRAYSCALE)
        imagem = cv2.resize(imagem, TAMANHO_AMOSTRA)
        faces.append(imagem)
        rotulos.append(mapa_nome_para_rotulo[nome])

    return faces, np.array(rotulos), mapa_nome_para_rotulo


def salvar_mapa_nomes(mapa_nome_para_rotulo):
    """Grava o mapeamento rótulo,nome em disco para o assistente carregar depois."""
    os.makedirs(os.path.dirname(ARQUIVO_MAPA), exist_ok=True)
    with open(ARQUIVO_MAPA, "w", encoding="utf-8") as arquivo:
        for nome, rotulo in mapa_nome_para_rotulo.items():
            arquivo.write(f"{rotulo},{nome}\n")


if __name__ == "__main__":
    faces, rotulos, mapa = montar_dataset()

    eigen = cv2.face.EigenFaceRecognizer_create()
    eigen.train(faces, rotulos)
    eigen.write(ARQUIVO_MODELO)

    salvar_mapa_nomes(mapa)
    print(f"Modelo treinado e salvo em '{ARQUIVO_MODELO}'.")
    print(f"Mapeamento de nomes salvo em '{ARQUIVO_MAPA}'.")
