import os
import yaml
import json
import requests
# import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# --- Configurações ---
app = Flask(__name__)
TESTS_DIR = "tests"
MOCKSERVER_URL = "http://localhost:1080" # Garanta que o MockServer está rodando aqui

# Configurar a API do Gemini
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# llm_model = genai.GenerativeModel('gemini-1.5-flash')


# --- Funções Auxiliares ---

def setup_mockserver(expectations):
    """Limpa e configura as expectations no MockServer."""
    try:
        requests.put(f"{MOCKSERVER_URL}/mockserver/reset")
        if expectations:
            requests.put(f"{MOCKSERVER_URL}/mockserver/expectation", json=expectations)
        return {"status": "success"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Erro no MockServer: {e}"}

def call_agent(agent_call_config):
    """Executa a chamada para o agente de IA."""
    try:
        response = requests.request(
            method=agent_call_config.get('method', 'GET'),
            url=agent_call_config['url'],
            headers=agent_call_config.get('headers'),
            json=agent_call_config.get('body')
        )
        response.raise_for_status()
        return {"status": "success", "response_data": response.json(), "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}

def verify_mockserver(verifications):
    """Verifica as chamadas no MockServer."""
    if not verifications:
        return {"status": "success", "verified": True, "details": "Nenhuma verificação necessária."}
    try:
        response = requests.put(f"{MOCKSERVER_URL}/mockserver/verify", json=verifications)
        if response.status_code == 202:
            return {"status": "success", "verified": True}
        else:
            return {"status": "error", "verified": False, "details": response.text}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Erro na verificação do MockServer: {e}"}

def validate_with_llm(agent_response, validation_prompt):
    """Usa um LLM para validar a resposta do agente."""
    if not validation_prompt:
        return {"status": "success", "is_valid": None, "reasoning": "Nenhum prompt de validação fornecido."}
    
    full_prompt = f"""
    Contexto da validação: {validation_prompt}
    ---
    Resposta do Agente (em JSON):
    {json.dumps(agent_response, indent=2)}
    ---
    Com base no contexto, a resposta do agente está correta? Responda estritamente com "true" ou "false".
    """
    try:
        response = "" # llm_model.generate_content(full_prompt)
        result_text = response.text.strip().lower()
        return {"status": "success", "is_valid": result_text == "true", "reasoning": response.text}
    except Exception as e:
        return {"status": "error", "message": f"Erro na API do LLM: {e}"}

# --- Rotas da API e da Interface ---

@app.route('/')
def index():
    """Página principal que lista os grupos de testes."""
    test_groups = [f.replace('.yml', '') for f in os.listdir(TESTS_DIR) if f.endswith('.yml')]
    return render_template('index.html', test_groups=test_groups)

@app.route('/api/tests/<group_name>')
def get_test_group(group_name):
    """Carrega os dados de um arquivo YAML."""
    try:
        with open(os.path.join(TESTS_DIR, f"{group_name}.yml"), 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "Grupo de teste não encontrado."}), 404

@app.route('/api/run', methods=['POST'])
def run_tests():
    """Endpoint para executar os testes."""
    tests_to_run = request.json.get('tests', [])
    results = []

    for test in tests_to_run:
        test_result = {"test_name": test.get('test_name')}

        # 1. Configurar Mocks
        setup_result = setup_mockserver(test.get('mockserver_expectations'))
        if setup_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Setup)'
            test_result['details'] = setup_result['message']
            results.append(test_result)
            continue

        # 2. Chamar o Agente
        agent_result = call_agent(test.get('agent_call'))
        test_result['agent_request'] = test.get('agent_call')
        if agent_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Chamada do Agente)'
            test_result['agent_response'] = agent_result['message']
            results.append(test_result)
            continue
        test_result['agent_response'] = agent_result['response_data']
        
        # 3. Verificar Mocks
        verify_result = verify_mockserver(test.get('mockserver_verifications'))
        test_result['mock_verification'] = verify_result

        # 4. Validar com LLM
        llm_result = validate_with_llm(agent_result['response_data'], test.get('llm_validation_prompt'))
        test_result['llm_validation'] = llm_result

        # Status Final
        if verify_result.get('verified', False) and (llm_result.get('is_valid', True) is not False):
            test_result['status'] = 'SUCESSO'
        else:
            test_result['status'] = 'FALHOU'

        results.append(test_result)

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)