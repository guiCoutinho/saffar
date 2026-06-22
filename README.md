# Saffar — Automação de Mensagens WhatsApp

Aplicativo desktop para envio automatizado de mensagens personalizadas via WhatsApp Web.

## Requisitos

- Python 3.10 ou superior → [python.org/downloads](https://www.python.org/downloads/)
- Git (opcional, para clonar o repositório)

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/guiCoutinho/saffar.git
cd saffar
```

### 2. Instale as dependências Python

```bash
pip install -r requirements.txt
```

### 3. Gere o executável

```bash
python build.py
```

O arquivo `dist/Saffar.exe` será criado. Pode ser copiado para qualquer pasta ou enviado para outros usuários.

---

## Uso

Execute `dist/Saffar.exe` (ou `python main.py` para rodar sem gerar o .exe).

Na **primeira execução**, o app baixará automaticamente o Chromium (~150 MB). Isso ocorre uma única vez.

### Fluxo de uso

1. **Excel** — carregue uma planilha `.xlsx` com os contatos (deve ter uma coluna `telefone`, `celular` ou similar)
2. **Mensagem** — componha a mensagem usando os botões de placeholder para inserir campos da planilha
3. **WhatsApp** — clique em "Conectar WhatsApp" e escaneie o QR Code (apenas na primeira vez)
4. **Enviar** — defina o intervalo entre envios e clique em "Iniciar Envios"

### Formato da planilha

| nome | telefone | cidade |
|------|----------|--------|
| João | 5511999990000 | São Paulo |
| Maria | 5521988880000 | Rio de Janeiro |

- O número deve incluir o código do país (`55` para Brasil) e o DDD, sem espaços ou símbolos
- Qualquer coluna pode ser usada como placeholder na mensagem: `{{nome}}`, `{{cidade}}`, etc.

### Log de auditoria

Ao fim de cada sessão de envios, um arquivo `*_log.csv` é salvo na mesma pasta da planilha com o resultado de cada envio.

---

## Observações

- A sessão do WhatsApp é salva localmente após o primeiro login (não é necessário escanear o QR Code novamente)
- Os envios são feitos com intervalos aleatórios entre o mínimo e máximo definidos pelo usuário
- Em caso de falha em um contato, o app pula para o próximo e exibe o resumo de falhas ao fim
