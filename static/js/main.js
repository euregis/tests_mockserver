document.addEventListener('DOMContentLoaded', function () {
    // --- Variáveis Globais ---
    let currentGroupName = null;
    let lastRunResults = [];
    const editors = {};

    // --- Elementos do DOM ---
    const groupList = document.getElementById('test-groups-list');
    const editorContainer = document.getElementById('test-editor-container');
    const welcomeMessage = document.getElementById('welcome-message');
    const groupTitle = document.getElementById('current-group-title');
    const testListContainer = document.getElementById('test-list-container');
    const resultsSection = document.getElementById('results-section');
    const resultsContainer = document.getElementById('results-container');
    const detailsModal = new bootstrap.Modal(document.getElementById('detailsModal'));
    const detailsModalContent = document.getElementById('detailsModalContent');
    const detailsModalTitle = document.getElementById('detailsModalTitle');

    // --- Funções do Editor ACE ---
    function createEditor(elementId, content, mode = 'json') {
        if (editors[elementId]) {
            editors[elementId].destroy();
        }
        const editor = ace.edit(elementId);
        editor.setTheme("ace/theme/tomorrow_night");
        editor.session.setMode(`ace/mode/${mode}`);

        let initialValue = content;
        if (mode === 'json' && (typeof content !== 'string')) {
            initialValue = JSON.stringify(content, null, 2);
        }
        editor.setValue(initialValue, -1);

        editor.setOptions({
            fontSize: "14px",
            showPrintMargin: false,
            useWorker: false
        });
        editors[elementId] = editor;
    }

    // --- Funções de API ---
    async function apiCall(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        const responseBody = await response.json();
        if (!response.ok) {
            throw new Error(responseBody.error || `HTTP error! status: ${response.status}`);
        }
        return responseBody;
    }

    // --- Funções de Renderização ---
    function renderGroupList(groups) {
        groupList.innerHTML = '';
        if (groups.length === 0) {
            groupList.innerHTML = '<div class="list-group-item">Nenhum grupo encontrado.</div>';
        }
        groups.forEach(group => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action';
            item.href = '#';
            item.textContent = group;
            item.dataset.group = group;
            if (group === currentGroupName) {
                item.classList.add('active');
            }
            groupList.appendChild(item);
        });
    }

    function renderTest(test, index) {
        const testId = `test-${index}`;
        const template = `
            <div class="card mb-3" data-test-index="${index}">
                <div class="card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="form-check d-flex align-items-center w-100">
                            <input class="form-check-input test-checkbox" type="checkbox" value="${index}" id="check-${testId}" checked>
                            <label class="form-check-label w-100 ms-2" for="check-${testId}">
                                <input type="text" class="form-control-plaintext form-control-sm test-name-input" value="${test.test_name || ''}" placeholder="Nome do Teste">
                            </label>
                        </div>
                        <button class="btn btn-sm btn-outline-danger delete-test-btn" title="Excluir Teste"><i class="bi bi-trash"></i></button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="accordion" id="accordion-${testId}">
                        ${renderAccordionItem(testId, 'setup-steps', '1. Passos de Setup (Login, etc)', test.setup_steps || [])}
                        ${renderAccordionItem(testId, 'expectations', '2. Expectations (MockServer)', test.mockserver_expectations || [])}
                        ${renderAccordionItem(testId, 'agent-call', '3. Chamada Principal ao Agente', test.agent_call || {})}
                        ${renderAccordionItem(testId, 'verifications', '4. Verifications (MockServer)', test.mockserver_verifications || [])}
                        ${renderAccordionItem(testId, 'llm-prompt', '5. Prompt de Validação (LLM)', test.llm_validation_prompt || "", 'text')}
                    </div>
                </div>
            </div>
        `;
        testListContainer.insertAdjacentHTML('beforeend', template);

        createEditor(`${testId}-setup-steps-editor`, test.setup_steps || []);
        createEditor(`${testId}-expectations-editor`, test.mockserver_expectations || []);
        createEditor(`${testId}-agent-call-editor`, test.agent_call || {});
        createEditor(`${testId}-verifications-editor`, test.mockserver_verifications || []);
        createEditor(`${testId}-llm-prompt-editor`, test.llm_validation_prompt || "", 'text');
    }

    function renderAccordionItem(testId, type, title, content, mode = 'json') {
        const editorId = `${testId}-${type}-editor`;
        return `
            <div class="accordion-item">
                <h2 class="accordion-header">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${testId}-${type}">
                        ${title}
                    </button>
                </h2>
                <div id="collapse-${testId}-${type}" class="accordion-collapse collapse">
                    <div class="accordion-body p-0">
                        <div id="${editorId}" class="editor"></div>
                    </div>
                </div>
            </div>
        `;
    }

    function renderResults(results) {
        resultsContainer.innerHTML = '';
        results.forEach((result, index) => {
            const statusClass = result.status === 'SUCESSO' ? 'status-success' : 'status-failed';
            const llmValid = result.llm_validation.is_valid === true ? '<span class="badge bg-success">Válido</span>' : (result.llm_validation.is_valid === false ? `<span class="badge bg-danger">Inválido</span>` : '<span class="badge bg-secondary">N/A</span>');
            const mockVerified = result.mock_verification.verified ? '<span class="badge bg-success">Verificado</span>' : (result.mock_verification.verified === false ? '<span class="badge bg-danger">Falhou</span>' : '<span class="badge bg-secondary">N/A</span>');

            const card = `
                <div class="card mb-3 ${statusClass}">
                    <div class="card-body">
                        <div class="d-flex justify-content-between">
                            <div>
                                <h5 class="card-title">${result.test_name}</h5>
                                <h6 class="card-subtitle mb-2">Status: <strong class="${result.status === 'SUCESSO' ? 'text-success' : 'text-danger'}">${result.status}</strong></h6>
                            </div>
                            <div>
                                ${mockVerified} ${llmValid}
                                <button class="btn btn-sm btn-outline-info view-details-btn" data-result-index="${index}" title="Ver Detalhes"><i class="bi bi-search"></i> Detalhes</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            resultsContainer.insertAdjacentHTML('beforeend', card);
        });
    }

    // --- Funções de Lógica ---
    async function loadGroups() {
        try {
            const groups = await apiCall('/api/test-groups');
            renderGroupList(groups);
        } catch (error) {
            alert(`Erro ao carregar grupos: ${error.message}`);
        }
    }

    async function selectGroup(groupName) {
        if (!groupName) {
            currentGroupName = null;
            editorContainer.classList.add('d-none');
            welcomeMessage.classList.remove('d-none');
            return;
        }
        try {
            const data = await apiCall(`/api/test-groups/${groupName}`);
            currentGroupName = groupName;
            groupTitle.textContent = `Grupo: ${groupName}`;
            testListContainer.innerHTML = '';
            Object.keys(editors).forEach(key => editors[key].destroy());
            data.forEach(renderTest);
            editorContainer.classList.remove('d-none');
            welcomeMessage.classList.add('d-none');
            loadGroups();
        } catch (error) {
            alert(`Erro ao carregar o grupo '${groupName}': ${error.message}`);
        }
    }

    function collectDataFromDOM() {
        const tests = [];
        document.querySelectorAll('#test-list-container .card').forEach((card) => {
            const testIndex = card.dataset.testIndex;

            let setupSteps, expectations, agentCall, verifications;
            try {
                setupSteps = JSON.parse(editors[`test-${testIndex}-setup-steps-editor`].getValue() || '[]');
                expectations = JSON.parse(editors[`test-${testIndex}-expectations-editor`].getValue() || '[]');
                agentCall = JSON.parse(editors[`test-${testIndex}-agent-call-editor`].getValue() || '{}');
                verifications = JSON.parse(editors[`test-${testIndex}-verifications-editor`].getValue() || '[]');
            } catch (e) {
                alert(`Erro de sintaxe JSON no teste '${card.querySelector('.test-name-input').value}'. Por favor, corrija. Erro: ${e.message}`);
                throw e;
            }

            const test = {
                test_name: card.querySelector('.test-name-input').value,
                setup_steps: setupSteps,
                mockserver_expectations: expectations,
                agent_call: agentCall,
                mockserver_verifications: verifications,
                llm_validation_prompt: editors[`test-${testIndex}-llm-prompt-editor`].getValue()
            };
            tests.push(test);
        });
        return tests;
    }

    // --- Handlers de Eventos ---
    groupList.addEventListener('click', e => {
        if (e.target.matches('.list-group-item')) {
            e.preventDefault();
            selectGroup(e.target.dataset.group);
        }
    });

    document.getElementById('new-group-btn').addEventListener('click', () => {
        const groupName = prompt("Digite o nome do novo grupo de testes (letras, números, - e _):");
        if (groupName && /^[a-zA-Z0-9_-]+$/.test(groupName)) {
            apiCall(`/api/test-groups/${groupName}`, 'POST', []).then(() => {
                selectGroup(groupName);
            }).catch(error => alert(`Erro ao criar grupo: ${error.message}`));
        } else if (groupName) {
            alert("Nome de grupo inválido.");
        }
    });

    document.getElementById('save-group-btn').addEventListener('click', () => {
        if (!currentGroupName) return;
        try {
            const dataToSave = collectDataFromDOM();
            apiCall(`/api/test-groups/${currentGroupName}`, 'POST', dataToSave)
                .then(() => alert(`Grupo '${currentGroupName}' salvo com sucesso!`))
                .catch(error => alert(`Erro ao salvar: ${error.message}`));
        } catch (e) {
            // O erro já foi mostrado pelo alert
        }
    });

    document.getElementById('delete-group-btn').addEventListener('click', () => {
        if (!currentGroupName || !confirm(`Tem certeza que deseja excluir o grupo '${currentGroupName}'?`)) return;
        apiCall(`/api/test-groups/${currentGroupName}`, 'DELETE')
            .then(() => {
                selectGroup(null);
                loadGroups();
            })
            .catch(error => alert(`Erro ao excluir: ${error.message}`));
    });

    document.getElementById('add-test-btn').addEventListener('click', () => {
        const newTest = {
            test_name: "Novo Teste Encadeado",
            setup_steps: [],
            mockserver_expectations: [],
            agent_call: {},
            mockserver_verifications: [],
            llm_validation_prompt: ""
        };
        const newIndex = document.querySelectorAll('#test-list-container .card').length;
        renderTest(newTest, newIndex);
    });

    testListContainer.addEventListener('click', e => {
        if (e.target.closest('.delete-test-btn')) {
            const card = e.target.closest('.card');
            if (confirm('Tem certeza que deseja remover este teste?')) {
                card.remove();
                document.querySelectorAll('#test-list-container .card').forEach((c, i) => c.dataset.testIndex = i);
            }
        }
    });

    document.getElementById('run-selected-tests-btn').addEventListener('click', async () => {
        let testsFromDOM;
        try {
            testsFromDOM = collectDataFromDOM();
        } catch (e) {
            return;
        }

        const testsToRun = [];
        document.querySelectorAll('.test-checkbox:checked').forEach(checkbox => {
            testsToRun.push(testsFromDOM[checkbox.value]);
        });

        if (testsToRun.length === 0) {
            alert('Selecione ao menos um teste para executar.');
            return;
        }

        resultsSection.classList.remove('d-none');
        resultsContainer.innerHTML = '<div class="text-center p-4"><div class="spinner-border" role="status"></div><p class="mt-2">Executando testes...</p></div>';

        try {
            const results = await apiCall('/api/run', 'POST', { tests: testsToRun });
            lastRunResults = results;
            renderResults(results);
        } catch (error) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Erro na execução: ${error.message}</div>`;
        }
    });

    resultsContainer.addEventListener('click', e => {
        const button = e.target.closest('.view-details-btn');
        if (button) {
            const resultIndex = button.dataset.resultIndex;
            const result = lastRunResults[resultIndex];
            detailsModalTitle.textContent = `Detalhes: ${result.test_name}`;
            detailsModalContent.textContent = JSON.stringify(result, null, 2);
            detailsModal.show();
        }
    });

    function exportData(format) {
        if (lastRunResults.length === 0) {
            alert("Nenhum resultado para exportar.");
            return;
        }
        fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: lastRunResults, format: format })
        })
            .then(res => {
                if (!res.ok) throw new Error("Falha na resposta do servidor");
                const disposition = res.headers.get('Content-Disposition');
                const filename = disposition ? disposition.split('filename=')[1] : `relatorio.${format}`;
                return Promise.all([res.blob(), filename]);
            })
            .then(([blob, filename]) => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
            })
            .catch(err => alert(`Erro ao exportar: ${err.message}`));
    }

    document.getElementById('export-json-btn').addEventListener('click', () => exportData('json'));
    document.getElementById('export-csv-btn').addEventListener('click', () => exportData('csv'));

    // --- Inicialização ---
    loadGroups();
});