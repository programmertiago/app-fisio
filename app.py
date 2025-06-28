# app.py
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# --- Configuração Inicial do Aplicativo ---
app = Flask(__name__)
# Chave secreta para segurança da sessão. Em um app real, use um valor complexo e secreto.
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-trocar-depois'
DB_NAME = 'hospital.db'

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redireciona para a rota 'login' se o usuário não estiver logado

# --- Modelo de Usuário ---
class Usuario(UserMixin):
    def __init__(self, id, nome_completo, email, funcao):
        self.id = id
        self.nome_completo = nome_completo
        self.email = email
        self.funcao = funcao

@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário a partir do ID da sessão."""
    conn = get_db_connection()
    user_data = conn.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user_data:
        return Usuario(id=user_data['id'], nome_completo=user_data['nome_completo'], email=user_data['email'], funcao=user_data['funcao'])
    return None

# --- Função de Conexão com o Banco ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = get_db_connection()
        user_data = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user_data and check_password_hash(user_data['senha_hash'], senha):
            usuario = Usuario(id=user_data['id'], nome_completo=user_data['nome_completo'], email=user_data['email'], funcao=user_data['funcao'])
            login_user(usuario) # Cria a sessão para o usuário
            return redirect(url_for('painel_diario'))
        else:
            flash('Email ou senha inválidos. Tente novamente.')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS PROTEGIDAS DO APLICATIVO ---

@app.route('/')
@login_required # <-- Proteção!
def painel_diario():
    # ... (o resto da função continua exatamente igual)
    hoje_str = date.today().isoformat()
    conn = get_db_connection()
    pacientes_ativos_raw = conn.execute("SELECT * FROM pacientes WHERE status = 'Ativo' ORDER BY unidade, nome").fetchall()
    atendimentos_hoje_raw = conn.execute("SELECT * FROM atendimentos WHERE data = ?", (hoje_str,)).fetchall()
    atendimentos_hoje = { at['paciente_id']: {'manha': at['turno_manha'], 'tarde': at['turno_tarde']} for at in atendimentos_hoje_raw }
    conn.close()
    painel = {}
    for p_raw in pacientes_ativos_raw:
        p = dict(p_raw)
        unidade = p['unidade']
        if unidade not in painel:
            painel[unidade] = []
        p['atendimentos_hoje'] = atendimentos_hoje.get(p['id'], {'manha': False, 'tarde': False})
        painel[unidade].append(p)
    return render_template('painel_diario.html', painel=painel, hoje=hoje_str)

@app.route('/paciente/<int:paciente_id>')
@login_required # <-- Proteção!
def detalhes_paciente(paciente_id):
    # ... (o resto da função continua exatamente igual)
    conn = get_db_connection()
    paciente = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
    evolucoes = conn.execute("SELECT * FROM evolucoes WHERE paciente_id = ? ORDER BY id DESC", (paciente_id,)).fetchall()
    conn.close()
    if paciente is None:
        return "Paciente não encontrado", 404
    return render_template('paciente.html', paciente=paciente, evolucoes=evolucoes)

@app.route('/adicionar_evolucao/<int:paciente_id>', methods=['POST'])
@login_required # <-- Proteção!
def adicionar_evolucao(paciente_id):
    conn = get_db_connection()
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Usamos o nome do usuário logado!
    fisio_logado = current_user.nome_completo

    conn.execute(
        "INSERT INTO evolucoes (paciente_id, data, fisio, texto) VALUES (?, ?, ?, ?)",
        (paciente_id, agora_str, fisio_logado, request.form['evolucao'])
    )
    
    # ... (o resto da lógica para marcar o atendimento continua igual)
    hoje_str = date.today().isoformat()
    turno = request.form['turno_atendimento']
    coluna_turno = 'turno_manha' if turno == 'manha' else 'turno_tarde'
    atendimento_existente = conn.execute("SELECT id FROM atendimentos WHERE paciente_id = ? AND data = ?", (paciente_id, hoje_str)).fetchone()
    if atendimento_existente:
        conn.execute(f"UPDATE atendimentos SET {coluna_turno} = 1 WHERE id = ?", (atendimento_existente['id'],))
    else:
        conn.execute(f"INSERT INTO atendimentos (paciente_id, data, {coluna_turno}) VALUES (?, ?, 1)",(paciente_id, hoje_str))
    
    conn.commit()
    conn.close()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

# --- Outras rotas (cadastro, gestão, etc.) também protegidas ---
# Adicionei o @login_required em todas as rotas que precisam de autenticação.

@app.route('/adicionar_paciente')
@login_required
def adicionar_paciente():
    return render_template('adicionar_paciente.html')

@app.route('/salvar_paciente', methods=['POST'])
@login_required
def salvar_paciente():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO pacientes (nome, idade, leito, unidade, diagnostico) VALUES (?, ?, ?, ?, ?)",
        (request.form['nome'], request.form['idade'], request.form['leito'], request.form['unidade'], request.form['diagnostico'])
    )
    conn.commit()
    conn.close()
    return redirect(url_for('painel_diario'))

@app.route('/marcar_atendimento', methods=['POST'])
@login_required
def marcar_atendimento():
    # ... (código inalterado)
    paciente_id = int(request.form['paciente_id'])
    data_atendimento = request.form['data']
    turno = request.form['turno']
    coluna_turno = 'turno_manha' if turno == 'manha' else 'turno_tarde'
    conn = get_db_connection()
    atendimento_existente = conn.execute("SELECT * FROM atendimentos WHERE paciente_id = ? AND data = ?", (paciente_id, data_atendimento)).fetchone()
    if atendimento_existente:
        status_atual = atendimento_existente[coluna_turno]
        conn.execute(f"UPDATE atendimentos SET {coluna_turno} = ? WHERE id = ?", (1 - status_atual, atendimento_existente['id']))
    else:
        conn.execute(f"INSERT INTO atendimentos (paciente_id, data, {coluna_turno}) VALUES (?, ?, 1)", (paciente_id, data_atendimento))
    conn.commit()
    conn.close()
    return redirect(url_for('painel_diario'))

@app.route('/mudar_unidade/<int:paciente_id>', methods=['POST'])
@login_required
def mudar_unidade(paciente_id):
    # ... (código inalterado)
    conn = get_db_connection()
    conn.execute("UPDATE pacientes SET unidade = ? WHERE id = ?", (request.form['unidade'], paciente_id))
    conn.commit()
    conn.close()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

@app.route('/inativar_paciente/<int:paciente_id>', methods=['POST'])
@login_required
def inativar_paciente(paciente_id):
    # ... (código inalterado)
    conn = get_db_connection()
    conn.execute("UPDATE pacientes SET status = 'Inativo', motivo_inativacao = ? WHERE id = ?", (request.form['motivo'], paciente_id))
    conn.commit()
    conn.close()
    return redirect(url_for('painel_diario'))

# --- Execução do Aplicativo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)