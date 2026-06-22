# Planejamento — App de Automação WhatsApp

## Objetivo
Aplicativo desktop Windows para automação de envio de mensagens personalizadas via WhatsApp Web, com input de planilha Excel e interface gráfica.

## Fluxo do usuário
1. Carregar planilha Excel (cada coluna é um campo: nome, telefone, cidade, etc.)
2. Compor mensagem personalizada usando placeholders das colunas
3. Conectar o WhatsApp Web (escanear QR code na primeira vez)
4. Configurar intervalo de tempo entre envios
5. Iniciar envios e acompanhar progresso
6. Ao fim, revisar log de falhas

## Decisões de design

| Aspecto | Decisão |
|---|---|
| Automação | WhatsApp Web via Playwright (Chromium) |
| Sessão | Persistida via `launch_persistent_context` — QR code escaneado apenas uma vez |
| Chromium | Baixado automaticamente na primeira execução (`playwright install chromium`) |
| Plataforma | Windows apenas (por enquanto) |
| Distribuição | Empacotado como `.exe` via PyInstaller |
| Volume esperado | Dezenas de envios por sessão |
| Intervalo entre envios | Range configurável pelo usuário (campo "mínimo" e "máximo" em segundos) |
| Aleatoriedade | `random.uniform(min, max)` a cada envio |
| Comportamento humano | Pesquisar número na barra de busca → abrir conversa → colar mensagem → enviar |
| Falhas de envio | Pula o contato, continua os demais, exibe resumo de falhas ao fim da sessão |
| Log de auditoria | CSV com: status, nome, telefone, timestamp, motivo do erro (apenas resultado final) |
| Interface | Abas sequenciais via `CTkTabview` |
| Placeholders | Botões gerados dinamicamente a partir das colunas do Excel — clique insere no cursor |
| Conexão WhatsApp | Botão explícito "Conectar WhatsApp" (não abre automaticamente ao entrar na aba) |
| Autenticação/licença | Nenhuma |

## Estrutura de abas
1. **Carregar Excel** — seleção de arquivo, preview das colunas detectadas
2. **Compor Mensagem** — área de texto + botões de placeholder por coluna
3. **Conectar WhatsApp** — botão para abrir navegador e exibir status da conexão
4. **Enviar** — configuração do intervalo (min/max), botão iniciar, progresso em tempo real, log de falhas ao fim

## Stack técnica
- `customtkinter` — interface gráfica
- `pandas` + `openpyxl` — leitura e parsing do Excel
- `playwright` — automação do WhatsApp Web
- `csv` (nativo Python) — log de auditoria
- `PyInstaller` — empacotamento em `.exe`

## Observações
- O `user_data_dir` da sessão Playwright será salvo em `%APPDATA%\NomeDoApp\session`
- O app deve rodar `playwright install chromium` na primeira inicialização, exibindo uma tela de "configurando, aguarde..."
- Intervalos sugeridos como padrão: mínimo 10s, máximo 30s (seguro para dezenas de envios)
- O log CSV deve ser salvo na mesma pasta do arquivo Excel ou em local configurável
