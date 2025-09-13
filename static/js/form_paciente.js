// Espera que todo o conteúdo da página seja carregado antes de executar o script
document.addEventListener('DOMContentLoaded', function() {

    // --- PASSO 1: LER OS DADOS DO HTML ---
    // Encontramos o container do formulário que tem os nossos dados
    const formContainer = document.querySelector('.form-container');
    // Lemos o atributo 'data-paciente' e convertemo-lo de uma string JSON para um objeto JavaScript
    const paciente = JSON.parse(formContainer.dataset.paciente);

    // --- O RESTO DO TEU CÓDIGO (AGORA NUM AMBIENTE JS PURO) ---

    // Referências aos nossos elementos HTML importantes
    const unidadeSelect = document.getElementById('unidade');
    const leitoContainer = document.getElementById('leito-container');

    function atualizarCampoLeito() {
        const unidadeSelecionada = unidadeSelect.value;
        const leitoAtual = paciente ? paciente.leito : '';

        leitoContainer.innerHTML = '';

        if (unidadeSelecionada === '1ª Enfermaria') {
            let select = document.createElement('select');
            select.id = 'leito';
            select.name = 'leito';
            select.required = true;

            for (let i = 101; i <= 114; i++) {
                let option = document.createElement('option');
                option.value = i;
                // Usamos a concatenação para evitar qualquer erro de linter
                option.textContent = 'Leito ' + i;
                if (String(i) === leitoAtual) {
                    option.selected = true;
                }
                select.appendChild(option);
            }
            leitoContainer.appendChild(select);

        } else if (unidadeSelecionada === 'UTI') {
            let select = document.createElement('select');
            select.id = 'leito';
            select.name = 'leito';
            select.required = true;

            for (let i = 1; i <= 6; i++) {
                let option = document.createElement('option');
                option.value = i;
                option.textContent = 'Leito ' + i;
                if (String(i) === leitoAtual) {
                    option.selected = true;
                }
                select.appendChild(option);
            }
            leitoContainer.appendChild(select);
        } else {
            leitoContainer.innerHTML = '<input type="text" id="leito" name="leito" value="' + leitoAtual + '" required>';
        }
    }

    // Adiciona os "ouvintes" de eventos
    unidadeSelect.addEventListener('change', atualizarCampoLeito);
    
    // Executa a função uma vez para o estado inicial
    atualizarCampoLeito();

    const dataNascimentoInput = document.getElementById('data_nascimento');
    dataNascimentoInput.addEventListener('input', function (e) {
        let value = e.target.value.replace(/\D/g, '');
        
        if (value.length > 8) {
            value = value.slice(0, 8);
        }

        if (value.length > 4) {
            value = value.slice(0, 2) + '/' + value.slice(2, 4) + '/' + value.slice(4);
        } else if (value.length > 2) {
            value = value.slice(0, 2) + '/' + value.slice(2);
        }

        e.target.value = value;
    });
});