# Material Circulante (Android / Python)

App de controle de material circulante (antigo **Neon Cart**), em Python com
[Kivy](https://kivy.org). Gera APK com [Buildozer](https://buildozer.readthedocs.io).

O **menu inicial** tem dois módulos: **CART** (baixa de carrinhos, abaixo) e
**PORTA VASOS** (devolução de material circulante).

## Porta Vasos

Devolução de material organizada em **pastas semanais**.

- **Pastas**: uma por semana (padrão domingo a sábado, ex.: `SEMANA 08.11 - 14.11`;
  nome e datas editáveis). Atalhos SEMANA PASSADA / ESTA SEMANA / PRÓXIMA.
  Filtro TODAS / AGUARDANDO / DEVOLVIDAS.
- **Status** de cada pasta: **AGUARDANDO DEVOLUÇÃO** ou **DEVOLVIDO** (com a data);
  toque no status para trocar.
- **Dentro da pasta**: devoluções com cliente, data e quantidade de cada material
  (DIVISÓRIAS, CESTO MOD 1/2, SUP MOD 2, SUP LONGO MOD 2, PTV P06, P09, P11, P13,
  P15, P17, PTV C21, CEST MULTI). Editar/excluir com desfazer.
- **Carrinhos**: cada carrinho é bipado (câmera, modo contínuo) ou tem o código
  digitado; a quantidade é o número de códigos. O mesmo código não entra duas
  vezes na mesma pasta.
- **Mesmo cliente, várias devoluções**: cada devolução é um registro com a sua
  data (ex.: AURORA 12 P11 hoje, 14 P13 amanhã). O formulário avisa quando o
  cliente já devolveu na pasta e a lista marca "1ª / 2ª DEVOLUÇÃO".
- **Cliente**: digitar o nome ou escolher na **LISTA** (buscar, cadastrar novo,
  remover da lista), além dos atalhos dos recentes.
- **Fotos**: tirar foto (câmera do app, várias seguidas) ou escolher da galeria;
  miniaturas no registro; visualizador com girar e excluir. As fotos ficam na
  pasta privada do app e **não** entram no backup `.json`.
- **Cliente individual**: COPIAR (área de transferência, para colar no WhatsApp)
  ou ENVIAR (texto, ou texto + fotos).
- **Imprimir**: gera PDF (A4 paisagem) com cabeçalho, status, tabela por cliente,
  total da pasta, resumo por cliente e campo de conferência/assinatura, e abre no
  leitor de PDF do celular (que tem a opção Imprimir). Da lista de pastas ou do
  resumo, imprime várias pastas com uma capa de resumo.
- **Excel** (COM ou SEM fotos): uma aba por pasta (com aba RESUMO quando são
  várias). Em cada aba: DEVOLUÇÕES POR DIA (uma linha por devolução, com os
  códigos dos carrinhos) + TOTAL DA PASTA; RESUMO POR CLIENTE (cada devolução com
  a data e, se o cliente devolveu mais de uma vez, a linha TOTAL do cliente); e,
  com fotos, as fotos de cada cliente abaixo. Configurada para imprimir em uma
  página de largura.
- **Compartilhar**: texto organizado para WhatsApp, PDF ou Excel.
- **Resumo**: totais por material e por cliente (todas, aguardando ou devolvidas).
- As pastas entram no backup `.json` junto com os dados do Cart.

## Cart — funções

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
| `portavasos.py` | Porta Vasos: pastas, status, materiais, datas, totais (sem Kivy) |
| `reports.py` | Relatório em PDF das pastas (layout de impressão) |
| `pdfgen.py` | Gerador de PDF próprio, sem dependências (Helvetica, acentos) |
| `photos.py` | Fotos: salvar, miniaturas, girar, limpar não usadas, NV21 da câmera |
| `photo_capture.py` | Câmera do app para fotografar o material |
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
