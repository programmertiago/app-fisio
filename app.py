# app.py
import sqlite3
import secrets
import string
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

# --- Decorators Customizados ---
from functools import wraps

def admin_required(f):
    """
    Decorator que garante que o usuário logado é um administrador.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.funcao != 'admin':
            flash('Acesso negado. Você precisa ser um administrador para ver esta página.', 'error')
            return redirect(url_for('painel_diario'))
        return f(*args, **kwargs)
    return decorated_function

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

# --- ROTAS DA ÁREA DO ADMINISTRADOR ---

@app.route('/admin/usuarios')
@login_required
@admin_required
def lista_usuarios():
    conn = get_db_connection()
    usuarios = conn.execute('SELECT id, nome_completo, email, funcao FROM usuarios ORDER BY nome_completo').fetchall()
    conn.close()
    return render_template('admin/lista_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_usuario():
    if request.method == 'POST':
        # Coleta os dados do formulário
        nome = request.form['nome_completo']
        email = request.form['email']
        senha = request.form['senha']
        funcao = request.form['funcao']

        # Conecta ao banco e verifica se o email já existe para evitar duplicados
        conn = get_db_connection()
        usuario_existente = conn.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone()

        if usuario_existente:
            # Se o email já existe, avisa o admin e redireciona de volta
            flash('Este email já está cadastrado no sistema.', 'error')
            conn.close()
            return redirect(url_for('criar_usuario'))

        # Se o email for novo, criptografa a senha e insere no banco
        senha_hashed = generate_password_hash(senha)
        conn.execute(
            'INSERT INTO usuarios (nome_completo, email, senha_hash, funcao) VALUES (?, ?, ?, ?)',
            (nome, email, senha_hashed, funcao)
        )
        conn.commit()
        conn.close()

        # Avisa que deu tudo certo e redireciona para a lista de usuários
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('lista_usuarios'))

    # Se o método for GET (primeiro acesso à página), apenas mostra o formulário
    return render_template('admin/form_usuario.html')

# Adicione este bloco logo após a função criar_usuario()

@app.route('/admin/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    conn = get_db_connection()
    # Primeiro, busca o usuário que será editado para garantir que ele existe
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()

    if usuario is None:
        flash('Usuário não encontrado.', 'error')
        conn.close()
        return redirect(url_for('lista_usuarios'))

    if request.method == 'POST':
        # Coleta os dados do formulário
        nome = request.form['nome_completo']
        email = request.form['email']
        funcao = request.form['funcao']

        # Verifica se o novo email já pertence a OUTRO usuário
        usuario_existente = conn.execute('SELECT id FROM usuarios WHERE email = ? AND id != ?', (email, usuario_id)).fetchone()
        if usuario_existente:
            flash('Este email já está em uso por outro usuário.', 'error')
            conn.close()
            # Re-renderiza o formulário com os dados originais do usuário
            return render_template('admin/form_usuario.html', usuario=usuario)
        
        # Atualiza os dados no banco
        conn.execute(
            'UPDATE usuarios SET nome_completo = ?, email = ?, funcao = ? WHERE id = ?',
            (nome, email, funcao, usuario_id)
        )
        conn.commit()
        conn.close()
        
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('lista_usuarios'))

    # Se a requisição for GET, apenas mostra o formulário já preenchido
    conn.close()
    return render_template('admin/form_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/resetar_senha/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def resetar_senha(usuario_id):
    # Define os caracteres que podem ser usados na nova senha
    alfabeto = string.ascii_letters + string.digits + '!@#$%^&*'
    # Gera uma senha segura de 12 caracteres
    nova_senha = ''.join(secrets.choice(alfabeto) for i in range(12))

    # Criptografa a nova senha
    senha_hashed = generate_password_hash(nova_senha)

    conn = get_db_connection()
    # Atualiza a senha do usuário no banco de dados
    conn.execute('UPDATE usuarios SET senha_hash = ? WHERE id = ?', (senha_hashed, usuario_id))

    # Pega o nome do usuário para a mensagem de feedback
    usuario = conn.execute('SELECT nome_completo FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()

    conn.commit()
    conn.close()

    # Mostra a nova senha na tela UMA VEZ para o admin poder copiar
    flash(f"A nova senha para '{usuario['nome_completo']}' é: {nova_senha}", 'success')
    flash('Anote e envie ao usuário. Esta senha não será mostrada novamente.', 'warning')

    return redirect(url_for('lista_usuarios'))

# --- Execução do Aplicativo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)