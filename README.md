Claro, aqui está o `README.md` completo formatado como um único bloco de código.

# IA Test Harness - Ferramenta de Testes para Agentes de IA

## Visão Geral

O **IA Test Harness** é uma aplicação web completa projetada para automatizar o teste de agentes de Inteligência Artificial e outras APIs complexas. A ferramenta permite criar, gerenciar e executar suítes de teste que validam não apenas as respostas de uma API, mas também as interações que ela realiza com serviços externos (dependências).

Com esta ferramenta, é possível simular o comportamento de dependências usando o **MockServer**, executar chamadas em múltiplos passos (como fluxos de login), e até mesmo usar um **Large Language Model (LLM)** como o Gemini para validar semanticamente se a resposta do agente está correta e dentro do contexto esperado.

---

## Funcionalidades Principais

-   **Interface Web Completa**: Crie, edite, visualize e exclua grupos de teste e testes individuais diretamente no navegador.
-   **Configuração em YAML**: Os testes são definidos em arquivos `.yml` de fácil leitura e versionáveis com Git.
-   **Integração com MockServer**: Configure `expectations` (mocks) e realize `verifications` (verificações) para garantir que seu agente está interagindo corretamente com suas dependências.
-   **Validação Semântica com LLM**: Forneça um prompt para que um LLM (Google Gemini) analise a resposta do seu agente e valide se ela cumpre os requisitos de negócio, indo além de uma simples comparação de dados.
-   **Testes em Múltiplos Passos (Encadeamento)**: Execute etapas de configuração (`setup_steps`), como um login, e capture dados da resposta (ex: um token de autenticação) para usar em chamadas subsequentes.
-   **Suporte a Segredos e Variáveis de Ambiente**: Mantenha suas credenciais (usuários, senhas, tokens) seguras, carregando-as a partir de variáveis de ambiente em vez de escrevê-las diretamente nos arquivos de teste.
-   **Editor de Código Integrado**: Utilize o editor ACE para editar as configurações JSON e prompts com syntax highlighting.
-   **Relatórios e Exportação**: Visualize os resultados dos testes em tempo real e exporte os relatórios completos em formatos **JSON** ou **CSV**.

---

## Arquitetura

A aplicação funciona como um orquestrador central que interage com vários serviços:

```

\+-------------------+      1. Carrega/Salva      +-----------------+
|                   | \<------------------------\> |                 |
|  Frontend (Web)   |      (Arquivos .yml)       |      Backend    |
| (templates/static)|                            |  (Flask App)    |
|                   | \<------------------------\> |                 |
\+-------------------+      2. Executa Testes     +-----------------+
(API REST)                 |           |           |
|           |           | 3. Configura/Verifica
|           |           | Mocks
v           v           v
\+-------------+  +-----------+  +-------------+
|  Agente de  |  | MockServer|  |     LLM     |
| IA (SUT\*)   |  |           |  |  (Gemini)   |
\+-------------+  +-----------+  +-------------+

  * SUT: System Under Test (Sistema Sob Teste)

<!-- end list -->

```

1.  O **Frontend** fornece a interface para o usuário gerenciar os testes.
2.  O **Backend (Flask)** serve o frontend, gerencia os arquivos `.yml` e orquestra a execução dos testes.
3.  Durante a execução, o backend se comunica com:
    * O **MockServer** para simular dependências.
    * O **Agente de IA** (seu sistema) para executar a chamada principal.
    * O **LLM (Gemini)** para realizar a validação semântica.

---

## Estrutura do Projeto

```

/ia-test-harness/
|
|-- /static/
|   |-- /css/
|   |   |-- style.css         \# Estilos customizados
|   |-- /js/
|       |-- main.js           \# Lógica do frontend (CRUD, execução)
|
|-- /templates/
|   |-- index.html            \# Template principal da aplicação
|
|-- /tests/
|   |-- exemplo.yml           \# Arquivo de exemplo para um grupo de testes
|
|-- app.py                    \# Aplicação principal com Flask (backend)
|-- requirements.txt          \# Dependências Python
|-- .env                      \# Arquivo para variáveis de ambiente e segredos
|-- README.md                 \# Este arquivo

```

---

## Como Configurar e Executar

### Pré-requisitos

-   Python 3.8+
-   Pip (gerenciador de pacotes do Python)
-   Java (para rodar o MockServer)
-   MockServer (arquivo `.jar` standalone)
-   Uma chave de API do Google Gemini (disponível no [Google AI Studio](https://aistudio.google.com/))

### Passo 1: Clonar e Configurar o Ambiente

1.  **Clone o repositório** para a sua máquina local.

2.  **Crie e ative um ambiente virtual** (altamente recomendado):
    ```bash
    python -m venv venv
    # No Windows:
    venv\Scripts\activate
    # No macOS/Linux:
    source venv/bin/activate
    ```

3.  **Instale as dependências** do Python:
    ```bash
    pip install -r requirements.txt
    ```

### Passo 2: Configurar Variáveis de Ambiente

1.  **Crie um arquivo `.env`** na raiz do projeto. Este arquivo não deve ser versionado no Git.

2.  **Adicione suas credenciais** ao arquivo. Ele será usado para carregar a chave da API do Gemini e quaisquer outros segredos que seus testes precisem (como usuário e senha para login).

    ```text
    # .env
    
    # Chave de API obrigatória para validação com LLM
    GEMINI_API_KEY="SUA_CHAVE_DE_API_DO_GEMINI_AQUI"
    
    # Exemplo de segredos para seus testes de login
    AGENT_USERNAME="usuario_de_teste"
    AGENT_PASSWORD="senha_super_secreta_123"
    ```

### Passo 3: Iniciar os Serviços

Para que a aplicação funcione, você precisa ter **três componentes rodando simultaneamente**, cada um em seu próprio terminal.

1.  **Terminal 1: MockServer**
    Navegue até a pasta onde você salvou o JAR do MockServer e inicie-o.
    ```bash
    java -jar mockserver-netty-5.15.0-jar-with-dependencies.jar -serverPort 1080
    ```

2.  **Terminal 2: Seu Agente de IA (Sistema Sob Teste)**
    Inicie a sua aplicação que será testada. Certifique-se de que ela esteja acessível a partir da aplicação Flask (ex: rodando em `localhost` em uma porta específica).

3.  **Terminal 3: Aplicação de Testes (Flask)**
    Na raiz do projeto `ia-test-harness`, inicie a aplicação principal.
    ```bash
    python app.py
    ```

### Passo 4: Acessar a Ferramenta

Abra seu navegador e acesse: **`http://localhost:5000`**

Você verá a interface do IA Test Harness, pronta para uso.

---

## Estrutura do Arquivo de Teste (`.yml`)

Cada arquivo `.yml` na pasta `/tests` representa um **grupo de testes**. Dentro dele, há uma lista de testes individuais. Cada teste pode ter as seguintes seções:

```yaml
- test_name: "Nome descritivo e único para o teste"
  
  setup_steps: # (Opcional) Lista de passos a serem executados ANTES da chamada principal.
    - step_name: "Descrição do passo, ex: Realizar Login"
      request: # A configuração da chamada HTTP para este passo.
        method: "POST"
        url: "[http://exemplo.com/auth/login](http://exemplo.com/auth/login)"
        body:
          username: "$env:AGENT_USERNAME" # Usa a variável de ambiente AGENT_USERNAME
          password: "$env:AGENT_PASSWORD" # Usa a variável de ambiente AGENT_PASSWORD
      capture: # (Opcional) Captura valores da resposta deste passo para usar depois.
        # Salva o valor de 'data.token' da resposta na variável 'authToken'
        authToken: "data.token" 

  mockserver_expectations: # (Opcional) Lista de mocks a serem configurados no MockServer.
    - httpRequest:
        method: "GET"
        path: "/api/users/123"
      httpResponse:
        statusCode: 200
        body: { "name": "Ana" }

  agent_call: # A chamada principal para o seu agente de IA.
    method: "GET"
    url: "[http://exemplo.com/users/123/profile](http://exemplo.com/users/123/profile)"
    headers:
      # Usa a variável 'authToken' capturada no setup_step
      Authorization: "Bearer {{authToken}}" 

  mockserver_verifications: # (Opcional) Lista de verificações a serem feitas no MockServer APÓS a chamada.
    - httpRequest:
        method: "GET"
        path: "/api/users/123"
      times: # Verifica se a chamada foi feita exatamente uma vez.
        atLeast: 1
        atMost: 1

  llm_validation_prompt: > # (Opcional) O prompt para o LLM validar a resposta do agente.
    Analise a resposta. Ela deve conter uma saudação amigável para a usuária "Ana"
    e mencionar que o perfil dela está completo.
    Responda apenas com "true" ou "false".
```
