# app.py
# O coração da nossa aplicação Flask.
# Certifique-se de ter um arquivo .env na mesma pasta com sua GEMINI_API_KEY.

import os
import yaml
import json
import requests
import google.generativeai as genai
import csv
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações da Aplicação ---
app = Flask(__name__)
TESTS_DIR = "tests"
MOCKSERVER_URL = "http://localhost:1080"  # Garanta que o MockServer esteja rodando neste endereço

# Criar o diretório de testes se ele não existir
if not os.path.exists(TESTS_DIR):
    os.makedirs(TESTS_DIR)

# Configurar a API do Gemini
try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    llm_model = genai.GenerativeModel('gemini-1.5-flash')
    GEMINI_API_CONFIGURED = True
except Exception as e:
    print(f"AVISO: Não foi possível configurar a API do Gemini. A validação por LLM será desativada. Erro: {e}")
    GEMINI_API_CONFIGURED = False

# --- Funções Auxiliares de Teste ---

def setup_mockserver(expectations):
    """Limpa o MockServer e configura as novas expectations."""
    try:
        # Limpa todas as expectations e logs de requisições anteriores
        requests.put(f"{MOCKSERVER_URL}/mockserver/reset")
        if expectations:
            # O MockServer espera um array de expectations
            response = requests.put(f"{MOCKSERVER_URL}/mockserver/expectation", json=expectations)
            response.raise_for_status()
        return {"status": "success"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"Erro ao configurar o MockServer: {e}"}

def call_agent(agent_call_config):
    """Executa a chamada HTTP para o agente de IA."""
    try:
        response = requests.request(
            method=agent_call_config.get('method', 'GET'),
            url=agent_call_config['url'],
            headers=agent_call_config.get('headers'),
            params=agent_call_config.get('queryParams'),
            json=agent_call_config.get('body'),
            timeout=30  # Timeout de 30 segundos
        )
        response.raise_for_status()  # Lança uma exceção para status de erro (4xx ou 5xx)
        # Tenta decodificar como JSON, senão retorna o texto puro
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = response.text
        return {"status": "success", "response_data": response_data, "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e), "response_data": str(e)}

def verify_mockserver(verifications):
    """Verifica se as chamadas esperadas foram feitas ao MockServer."""
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
    """Usa um LLM para validar a resposta do agente com base em um prompt."""
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
    Com base estritamente no **Contexto da Validação** fornecido, a **Resposta do Agente** está correta e cumpre todos os requisitos?
    Responda apenas com a palavra "true" se estiver correta, ou "false" se não estiver. Não adicione nenhuma outra palavra ou pontuação.
    """
    try:
        response = llm_model.generate_content(full_prompt)
        result_text = response.text.strip().lower()
        is_valid = result_text == "true"
        return {"status": "success", "is_valid": is_valid, "reasoning": response.text}
    except Exception as e:
        return {"status": "error", "message": f"Erro na chamada à API do LLM: {e}", "is_valid": False}

# --- Rotas da Aplicação (Endpoints) ---

@app.route('/')
def index():
    """Renderiza a página principal da aplicação."""
    return render_template('index.html')

@app.route('/api/test-groups', methods=['GET'])
def get_test_groups():
    """Lista todos os grupos de teste (arquivos .yml)."""
    try:
        groups = [f.replace('.yml', '') for f in os.listdir(TESTS_DIR) if f.endswith('.yml')]
        return jsonify(sorted(groups))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test-groups/<group_name>', methods=['GET', 'POST', 'DELETE'])
def manage_test_group(group_name):
    """Gerencia um grupo de teste específico (CRUD)."""
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
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/run', methods=['POST'])
def run_tests():
    """Endpoint principal para executar os testes selecionados."""
    tests_to_run = request.json.get('tests', [])
    results = []

    for test_config in tests_to_run:
        test_result = {"test_name": test_config.get('test_name', 'Teste sem nome')}

        # 1. Configurar Mocks
        setup_result = setup_mockserver(test_config.get('mockserver_expectations'))
        if setup_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Setup do Mock)'
            test_result['details'] = setup_result['message']
            results.append(test_result)
            continue

        # 2. Chamar o Agente
        agent_call_config = test_config.get('agent_call', {})
        agent_result = call_agent(agent_call_config)
        test_result['agent_request'] = agent_call_config
        test_result['agent_response'] = agent_result
        
        if agent_result['status'] == 'error':
            test_result['status'] = 'FALHOU (Chamada do Agente)'
            results.append(test_result)
            continue
        
        # 3. Verificar Mocks
        verify_result = verify_mockserver(test_config.get('mockserver_verifications'))
        test_result['mock_verification'] = verify_result

        # 4. Validar com LLM
        llm_result = validate_with_llm(agent_result.get('response_data'), test_config.get('llm_validation_prompt'))
        test_result['llm_validation'] = llm_result

        # Status Final do Teste
        mock_ok = verify_result.get('verified', False)
        llm_ok = llm_result.get('is_valid', True) is not False # Considera N/A como sucesso
        
        if mock_ok and llm_ok:
            test_result['status'] = 'SUCESSO'
        else:
            test_result['status'] = 'FALHOU'

        results.append(test_result)

    return jsonify(results)

@app.route('/api/export', methods=['POST'])
def export_results():
    """Exporta os resultados dos testes para CSV ou JSON."""
    data = request.json
    results = data.get('results', [])
    export_format = data.get('format', 'json')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"relatorio_testes_{timestamp}"

    if export_format == 'json':
        return Response(
            json.dumps(results, indent=2, ensure_ascii=False),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment;filename={filename}.json'}
        )
    
    if export_format == 'csv':
        # Criar um buffer de string para o CSV
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        
        # Cabeçalho do CSV
        writer.writerow([
            "Nome do Teste", "Status Final", 
            "Status Chamada Agente", "Status Code Agente", "Resposta Agente",
            "Verificação Mock OK?", "Detalhes Verificação Mock",
            "Validação LLM OK?", "Razão Validação LLM"
        ])
        
        # Linhas do CSV
        for res in results:
            writer.writerow([
                res.get('test_name', ''),
                res.get('status', ''),
                res.get('agent_response', {}).get('status', ''),
                res.get('agent_response', {}).get('status_code', ''),
                json.dumps(res.get('agent_response', {}).get('response_data', ''), ensure_ascii=False),
                res.get('mock_verification', {}).get('verified', ''),
                json.dumps(res.get('mock_verification', {}).get('details', ''), ensure_ascii=False),
                res.get('llm_validation', {}).get('is_valid', ''),
                res.get('llm_validation', {}).get('reasoning', '')
            ])
            
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={filename}.csv'}
        )

    return jsonify({"error": "Formato de exportação inválido."}), 400


if __name__ == '__main__':
    # Roda a aplicação Flask em modo de debug
    app.run(debug=True, port=5000)