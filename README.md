# Neon Cart (Android / Python)

App de baixa de carrinhos convertido do app web (React) para Python com
[Kivy](https://kivy.org). Gera APK com [Buildozer](https://buildozer.readthedocs.io).

## Funções

**Lista (tela inicial)**
- Cadastro de carrinho: setor/divisória, código e observação (código e setor em maiúsculas).
- Setores recentes como atalhos de um toque.
- Bloqueio de código duplicado com alerta animado, bipe e vibração.
- Leitor de código de barras / QR pela câmera (pyzbar/zbar), com flash e troca de lente.
- **Modo contínuo**: a câmera fica aberta e registra cada código lido no setor atual.
- Busca; editar; excluir com **DESFAZER**; limpar tudo (com confirmação e desfazer).
- Exportar `.xlsx` (com aba de resumo por setor) para **Downloads**; compartilhar texto.

**Histórico de scans**
- Toda leitura da câmera, cadastro, duplicado, edição e exclusão, com data/hora e origem.
- Filtros (lidos, registrados, duplicados, editados, excluídos) e busca.
- Toque num item: mostra onde o código está e permite usá-lo de novo.
- Exportar histórico em `.xlsx`; limpar histórico.

**Listas salvas**
- Salvar a lista atual com nome (ex.: turno, inventário) e começar uma nova.
- Ver, compartilhar, exportar `.xlsx`, restaurar, renomear e excluir (com desfazer).

**Resumo**
- Totais da lista, registros/duplicados/leituras do dia, listas salvas e gráfico por setor.

**Ajustes**
- Modo contínuo, vibração e som.
- Backup completo (`.json`) para Downloads e importação de backup.
- Botão voltar do Android retorna à tela inicial.

Dados salvos em `neoncart.json` na pasta privada do app (migra o `entries.json` da versão 1).

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `main.py` | Ponto de entrada; mostra a tela de erro se o app falhar ao abrir |
| `neoncart_app.py` | App Kivy, telas e ações |
| `neoncart.kv` | Layout e tema neon |
| `storage.py` | Dados: lista, histórico, listas salvas, resumo, backup (sem Kivy) |
| `exporter.py` | Planilhas `.xlsx`, backup `.json` e textos para compartilhar |
| `scanner.py` | Câmera, decodificação e modo contínuo |
| `platform_utils.py` | Android via pyjnius: permissões, compartilhar, Downloads, flash, vibração, seletor de arquivo |
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
`assets/fonts/materialdesignicons-webfont.ttf`. Sons em `assets/sounds/` gerados pelo projeto.
