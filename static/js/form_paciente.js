document.addEventListener('DOMContentLoaded', function() {

    // --- LÓGICA PARA ATUALIZAÇÃO DINÂMICA DOS LEITOS ---

    // Alteramos a linha abaixo para usar getElementById, que é mais específico
    const formCard = document.getElementById('form-paciente-card');
    const paciente = JSON.parse(formCard.dataset.paciente);

    const unidadeSelect = document.getElementById('unidade');
    const leitoContainer = document.getElementById('leito-container');

    function atualizarCampoLeito() {
        const unidadeSelecionada = unidadeSelect.value;
        const leitoAtual = paciente ? paciente.leito : '';

        leitoContainer.innerHTML = '';

        if (unidadeSelecionada === '1ª Enfermaria' || unidadeSelecionada === 'UTI') {
            let select = document.createElement('select');
            select.id = 'leito';
            select.name = 'leito';
            select.className = 'form-select';
            select.required = true;

            let options = [];
            if (unidadeSelecionada === '1ª Enfermaria') {
                for (let i = 101; i <= 114; i++) { options.push(String(i)); }
            } else { // UTI
                for (let i = 1; i <= 6; i++) { options.push(String(i)); }
            }

            options.forEach(num => {
                let option = document.createElement('option');
                option.value = num;
                option.textContent = `Leito ${num}`;
                if (num === String(leitoAtual)) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
            
            leitoContainer.appendChild(select);

        } else {
            let input = document.createElement('input');
            input.type = 'text';
            input.id = 'leito';
            input.name = 'leito';
            input.className = 'form-control';
            input.value = leitoAtual;
            input.required = true;
            leitoContainer.appendChild(input);
        }
    }

    if (unidadeSelect) {
        unidadeSelect.addEventListener('change', atualizarCampoLeito);
    }
    
    if (formCard) { // Adicionamos uma verificação para segurança
        atualizarCampoLeito();
    }


    // --- LÓGICA PARA FORMATAÇÃO AUTOMÁTICA DA DATA ---
    const dataNascimentoInput = document.getElementById('data_nascimento');

    if (dataNascimentoInput) {
        dataNascimentoInput.addEventListener('input', function (e) {
            let value = e.target.value.replace(/\D/g, '');
            
            if (value.length > 8) { value = value.slice(0, 8); }

            if (value.length > 4) {
                value = value.slice(0, 2) + '/' + value.slice(2, 4) + '/' + value.slice(4);
            } else if (value.length > 2) {
                value = value.slice(0, 2) + '/' + value.slice(2);
            }

            e.target.value = value;
        });
    }
});