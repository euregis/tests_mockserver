# app.py
# EVOLUÇÃO: Adicionado suporte para 'setup_steps' para lidar com login e encadeamento.

import os
import yaml
import json
import requests
import google.generativeai as genai
import csv
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from datetime import datetime
from functools import reduce
import operator

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações da Aplicação ---
app = Flask(__name__)
TESTS_DIR = "tests"
MOCKSERVER_URL = "http://localhost:1080"

if not os.path.exists(TESTS_DIR):
    os.makedirs(TESTS_DIR)

try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    llm_model = genai.GenerativeModel('gemini-1.5-flash')
    GEMINI_API_CONFIGURED = True
except Exception as e:
    print(f"AVISO: Não foi possível configurar a API do Gemini. A validação por LLM será desativada. Erro: {e}")
    GEMINI_API_CONFIGURED = False

# --- Funções Auxiliares ---

def get_from_dict(data_dict, map_list):
    """Acessa um valor aninhado em um dicionário usando uma lista de chaves."""
    try:
        return reduce(operator.getitem, map_list, data_dict)
    except (KeyError, TypeError):
        return None

def substitute_variables(data, context):
    """
    Substitui recursivamente variáveis em um dicionário/lista.
    Suporta:
    - {{var_name}} do contexto de execução (chaining).
    - $env:VAR_NAME das variáveis de ambiente.
    """
    if isinstance(data, dict):
        return {k: substitute_variables(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_variables(i, context) for i in data]
    elif isinstance(data, str):
        # Primeiro, substitui variáveis de ambiente
        if data.startswith("$env:"):
            env_var_name = data[5:] # Pega o nome da variável depois de "$env:"
            data = os.getenv(env_var_name, '') # Pega o valor do ambiente
            if not data:
                print(f"AVISO: Variável de ambiente '{env_var_name}' não definida.")

        # Depois, substitui variáveis de contexto (para encadeamento)
        for key, value in context.items():
            data = data.replace(f"{{{{{key}}}}}", str(value))
        return data
    else:
        return data

def setup_mockserver(expectations):
    try:
        requests.put(f"{MOCKSERVER_URL}/mockserver/reset")
        if expectations:
            response = requests.put(f"{MOCKSERVER_URL}/mockserver/expectation", json=expectations)
            response.raise_for_status()
        return {"status": "success"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Erro ao configurar o MockServer: {e}"}

def call_api(call_config):
    """Função genérica para fazer uma chamada HTTP (usada por setup e agent_call)."""
    try:
        response = requests.request(
            method=call_config.get('method', 'GET'),
            url=call_config['url'],
            headers=call_config.get('headers'),
            params=call_config.get('queryParams'),
            json=call_config.get('body'),
            timeout=30
        )
        response.raise_for_status()
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = response.text
        return {"status": "success", "response_data": response_data, "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e), "response_data": str(e)}

def verify_mockserver(verifications):
    if not verifications:
        return {"status": "success", "verified": True, "details": "Nenhuma verificação necessária."}
    all_verified = True
    verification_details = []
    for verification in verifications:
        try:
            response = requests.put(f"{MOCKSERVER_URL}/mockserver/verify", json=verification)
            if response.status_code == 202:
                verification_details.append({"rule": verification, "status": "Verificado"})
            else:
                all_verified = False
                verification_details.append({"rule": verification, "status": "Falhou", "reason": response.text})
        except requests.exceptions.RequestException as e:
            all_verified = False
            verification_details.append({"rule": verification, "status": "Erro", "reason": str(e)})
    return {"status": "success" if all_verified else "error", "verified": all_verified, "details": verification_details}

def validate_with_llm(agent_response, validation_prompt):
    if not validation_prompt:
        return {"status": "success", "is_valid": None, "reasoning": "Nenhum prompt de validação fornecido."}
    if not GEMINI_API_CONFIGURED:
        return {"status": "error", "is_valid": None, "reasoning": "API do Gemini não configurada."}
    full_prompt = f"""
    **Contexto da Validação:**
    {validation_prompt}
    ---
    **Resposta do Agente a ser Analisada (em formato JSON):**
    {json.dumps(agent_response, indent=2, ensure_ascii=False)}
    ---
    Com base estritamente no **Contexto da Validação**, a resposta está correta? Responda apenas com "true" ou "false".
    """
    try:
        response = llm_model.generate_content(full_prompt)
        result_text = response.text.strip().lower()
        is_valid = result_text == "true"
        return {"status": "success", "is_valid": is_valid, "reasoning": response.text}
    except Exception as e:
        return {"status": "error", "message": f"Erro na chamada à API do LLM: {e}", "is_valid": False}

# --- Rotas da Aplicação ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/test-groups', methods=['GET'])
def get_test_groups():
    try:
        groups = [f.replace('.yml', '') for f in os.listdir(TESTS_DIR) if f.endswith('.yml')]
        return jsonify(sorted(groups))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test-groups/<group_name>', methods=['GET', 'POST', 'DELETE'])
def manage_test_group(group_name):
    if '..' in group_name or '/' in group_name:
        return jsonify({"error": "Nome de grupo inválido."}), 400
    filepath = os.path.join(TESTS_DIR, f"{group_name}.yml")
    if request.method == 'GET':
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or []
                return jsonify(data)
        except FileNotFoundError:
            return jsonify({"error": "Grupo de teste não encontrado."}), 404
    if request.method == 'POST':
        try:
            tests_data = request.json
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(tests_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            return jsonify({"success": True, "message": f"Grupo '{group_name}' salvo com sucesso."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    if request.method == 'DELETE':
        try:
            os.remove(filepath)
            return jsonify({"success": True, "message": f"Grupo '{group_name}' excluído."})
        except FileNotFoundError:
            return jsonify({"error": "Grupo de teste não encontrado."}), 404
    return jsonify({"error": "Método não permitido"}), 405

@app.route('/api/run', methods=['POST'])
def run_tests():
    tests_to_run = request.json.get('tests', [])
    results = []

    for test_config in tests_to_run:
        test_result = {"test_name": test_config.get('test_name', 'Teste sem nome'), "setup_steps_results": []}
        context = {}  # Contexto para armazenar variáveis (ex: token)

        # --- 1. Executar Setup Steps ---
        setup_failed = False
        if 'setup_steps' in test_config:
            for step in test_config.get('setup_steps', []):
                step_request_config = substitute_variables(step.get('request', {}), context)
                step_result = call_api(step_request_config)
                step_result['step_name'] = step.get('step_name', 'Passo sem nome')
                test_result["setup_steps_results"].append(step_result)

                if step_result['status'] == 'error':
                    test_result['status'] = f"FALHOU ({step_result['step_name']})"
                    setup_failed = True
                    break
                
                if 'capture' in step:
                    for var_name, json_path in step['capture'].items():
                        captured_value = get_from_dict(step_result['response_data'], json_path.split('.'))
                        if captured_value is not None:
                            context[var_name] = captured_value
                        else:
                            test_result['status'] = f"FALHOU (Captura da variável '{var_name}')"
                            setup_failed = True
                            break
            if setup_failed:
                results.append(test_result)
                continue
        
        # --- 2. Configurar Mocks ---
        mock_expectations = substitute_variables(test_config.get('mockserver_expectations', []), context)
        setup_result = setup_mockserver(mock_expectations)
        if setup_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Setup do Mock)'
            test_result['details'] = setup_result['message']
            results.append(test_result)
            continue

        # --- 3. Chamar o Agente ---
        agent_call_config = substitute_variables(test_config.get('agent_call', {}), context)
        agent_result = call_api(agent_call_config)
        test_result['agent_request'] = agent_call_config
        test_result['agent_response'] = agent_result
        
        if agent_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Chamada do Agente)'
            results.append(test_result)
            continue
        
        # --- 4. Verificar Mocks ---
        mock_verifications = substitute_variables(test_config.get('mockserver_verifications', []), context)
        verify_result = verify_mockserver(mock_verifications)
        test_result['mock_verification'] = verify_result

        # --- 5. Validar com LLM ---
        llm_result = validate_with_llm(agent_result.get('response_data'), test_config.get('llm_validation_prompt'))
        test_result['llm_validation'] = llm_result

        # --- Status Final ---
        mock_ok = verify_result.get('verified', False)
        llm_ok = llm_result.get('is_valid', True) is not False
        
        if mock_ok and llm_ok:
            test_result['status'] = 'SUCESSO'
        else:
            test_result['status'] = 'FALHOU'

        results.append(test_result)

    return jsonify(results)

# A rota /api/export permanece a mesma
@app.route('/api/export', methods=['POST'])
def export_results():
    data = request.json
    results = data.get('results', [])
    export_format = data.get('format', 'json')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"relatorio_testes_{timestamp}"
    if export_format == 'json':
        return Response(json.dumps(results, indent=2, ensure_ascii=False), mimetype='application/json', headers={'Content-Disposition': f'attachment;filename={filename}.json'})
    if export_format == 'csv':
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Nome do Teste", "Status Final", "Status Chamada Agente", "Status Code Agente", "Resposta Agente", "Verificação Mock OK?", "Detalhes Verificação Mock", "Validação LLM OK?", "Razão Validação LLM"])
        for res in results:
            writer.writerow([res.get('test_name', ''), res.get('status', ''), res.get('agent_response', {}).get('status', ''), res.get('agent_response', {}).get('status_code', ''), json.dumps(res.get('agent_response', {}).get('response_data', ''), ensure_ascii=False), res.get('mock_verification', {}).get('verified', ''), json.dumps(res.get('mock_verification', {}).get('details', ''), ensure_ascii=False), res.get('llm_validation', {}).get('is_valid', ''), res.get('llm_validation', {}).get('reasoning', '')])
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment;filename={filename}.csv'})
    return jsonify({"error": "Formato de exportação inválido."}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)