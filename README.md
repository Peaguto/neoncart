# Neon Cart (Android / Python)

App de baixa de carrinhos convertido do app web (React) para Python com
[Kivy](https://kivy.org). Gera APK com [Buildozer](https://buildozer.readthedocs.io).

## Funções

- Cadastro de carrinho: setor/divisória, código e observação (código e setor em maiúsculas).
- Bloqueio de código duplicado com alerta animado.
- Leitor de código de barras / QR pela câmera (pyzbar/zbar), com flash e troca de lente.
- Busca por código, divisória ou observação.
- Editar e excluir registros; limpar tudo (com confirmação).
- Exportar planilha Excel `.xlsx` para **Downloads** (e compartilhar o arquivo no Android 10+).
- Compartilhar relatório em texto (WhatsApp etc.) pelo menu de compartilhamento do Android.
- Dados salvos em JSON na pasta privada do app.

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `main.py` | App Kivy, telas e ações |
| `neoncart.kv` | Layout e tema neon |
| `storage.py` | Registros, duplicidade, busca, persistência (sem Kivy) |
| `exporter.py` | Planilha `.xlsx` e texto para compartilhar |
| `scanner.py` | Câmera + decodificação de código de barras |
| `platform_utils.py` | Android via pyjnius: permissões, compartilhar, Downloads, flash |
| `theme.py` | Cores, ícones e degradês |
| `buildozer.spec` | Configuração do APK |

## Rodar no computador (teste)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
.venv/bin/python -m pytest -q
```

O leitor precisa da lib nativa zbar (`sudo apt install libzbar0`). A câmera no
desktop precisa de OpenCV ou GStreamer; sem eles, o leitor mostra "CÂMERA INDISPONÍVEL".

## Compilar o APK

Buildozer roda em **Linux** (ou WSL2 no Windows; no macOS, use Docker).

```bash
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool \
  pkg-config zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev automake
pip install --user buildozer cython
buildozer -v android debug
```

O APK sai em `bin/`. A primeira compilação baixa Android SDK/NDK (vários GB) e demora.

## Licenças de terceiros

Ícones: Material Design Icons (Pictogrammers), licença Apache 2.0 —
`assets/fonts/materialdesignicons-webfont.ttf`.
