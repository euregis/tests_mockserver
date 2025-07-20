$(document).ready(function () {
    let currentTestData = [];

    // Carregar um grupo de testes ao clicar
    $('.load-group').on('click', function (e) {
        e.preventDefault();
        const groupName = $(this).data('group');
        $('#current-group-title').text(`Grupo: ${groupName}`);

        $.get(`/api/tests/${groupName}`, function (data) {
            currentTestData = data;
            const testListContainer = $('#test-list-container');
            testListContainer.empty();

            data.forEach((test, index) => {
                // Para cada teste, criar um card com um checkbox
                testListContainer.append(`
                    <div class="card mb-2">
                        <div class="card-body">
                            <div class="form-check">
                                <input class="form-check-input test-checkbox" type="checkbox" value="${index}" id="test-${index}">
                                <label class="form-check-label" for="test-${index}">
                                    <strong>${test.test_name}</strong>
                                </label>
                            </div>
                            <p class="card-text text-muted">${test.description || ''}</p>
                        </div>
                    </div>
                `);
            });
            $('#run-selected-tests').show();
        });
    });

    // Executar os testes selecionados
    $('#run-selected-tests').on('click', function () {
        const selectedTests = [];
        $('.test-checkbox:checked').each(function () {
            const testIndex = $(this).val();
            selectedTests.push(currentTestData[testIndex]);
        });

        if (selectedTests.length === 0) {
            alert('Selecione ao menos um teste para executar.');
            return;
        }

        // Mostrar um spinner/loading
        $('#results-container').html('<div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div>');

        // Chamar a API do backend para rodar
        $.ajax({
            url: '/api/run',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ tests: selectedTests }),
            success: function (results) {
                displayResults(results);
            },
            error: function () {
                $('#results-container').html('<div class="alert alert-danger">Ocorreu um erro ao executar os testes.</div>');
            }
        });
    });

    // Função para mostrar os resultados
    function displayResults(results) {
        const resultsContainer = $('#results-container');
        resultsContainer.empty();

        let table = `<table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>Nome do Teste</th>
                                <th>Status</th>
                                <th>Validação LLM</th>
                                <th>Verificação Mock</th>
                                <th>Detalhes</th>
                            </tr>
                        </thead>
                        <tbody>`;

        results.forEach(result => {
            const statusClass = result.status === 'SUCESSO' ? 'table-success' : 'table-danger';
            const llmValid = result.llm_validation.is_valid === true ? 'Válido' : (result.llm_validation.is_valid === false ? 'Inválido' : 'N/A');
            const mockVerified = result.mock_verification.verified ? 'Verificado' : 'Falhou';

            table += `<tr class="${statusClass}">
                        <td>${result.test_name}</td>
                        <td><strong>${result.status}</strong></td>
                        <td>${llmValid}</td>
                        <td>${mockVerified}</td>
                        <td><button class="btn btn-sm btn-info" onclick='alert(${JSON.stringify(JSON.stringify(result))})'>Ver JSON</button></td>
                      </tr>`;
        });

        table += `</tbody></table>`;
        resultsContainer.html(table);
    }
});