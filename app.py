# app.py (versão completa e finalizada - 07/Jul/2025)

import sqlite3
import secrets
import string
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pytz
from functools import wraps

# --- Configuração Inicial do Aplicativo ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-trocar-depois'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'hospital.db')

# --- Configuração do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Decorators Customizados ---
def admin_required(f):
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

@app.before_request
def check_force_password_change():
    if current_user.is_authenticated and request.endpoint not in ['logout', 'alterar_senha', 'static']:
        conn = get_db_connection()
        user_data = conn.execute('SELECT precisa_trocar_senha FROM usuarios WHERE id = ?', (current_user.id,)).fetchone()
        conn.close()
        if user_data and user_data['precisa_trocar_senha'] == 1:
            flash('Por segurança, você precisa definir uma nova senha antes de continuar.', 'warning')
            return redirect(url_for('alterar_senha'))

@login_manager.user_loader
def load_user(user_id):
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

# --- ROTAS DE AUTENTICAÇÃO E PERFIL ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        conn = get_db_connection()
        user_data = conn.execute("SELECT * FROM usuarios WHERE email = ? AND status = 'Ativo'", (email,)).fetchone()
        conn.close()
        if user_data and check_password_hash(user_data['senha_hash'], senha):
            usuario = Usuario(id=user_data['id'], nome_completo=user_data['nome_completo'], email=user_data['email'], funcao=user_data['funcao'])
            login_user(usuario)
            return redirect(url_for('painel_diario'))
        else:
            flash('Email ou senha inválidos, ou usuário inativo.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/alterar-senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    if request.method == 'POST':
        senha_atual = request.form['senha_atual']
        nova_senha = request.form['nova_senha']
        confirmacao = request.form['confirmacao_senha']
        conn = get_db_connection()
        user_db_data = conn.execute('SELECT senha_hash FROM usuarios WHERE id = ?', (current_user.id,)).fetchone()
        if not check_password_hash(user_db_data['senha_hash'], senha_atual):
            flash('Sua senha atual está incorreta. Tente novamente.', 'error')
            conn.close()
            return redirect(url_for('alterar_senha'))
        if nova_senha != confirmacao:
            flash('A nova senha e a confirmação não correspondem.', 'error')
            conn.close()
            return redirect(url_for('alterar_senha'))
        senha_hashed = generate_password_hash(nova_senha)
        conn.execute('UPDATE usuarios SET senha_hash = ?, precisa_trocar_senha = 0 WHERE id = ?', (senha_hashed, current_user.id))
        conn.commit()
        conn.close()
        flash('Sua senha foi alterada com sucesso!', 'success')
        return redirect(url_for('painel_diario'))
    return render_template('alterar_senha.html')

# --- ROTAS PRINCIPAIS DO APP ---
@app.route('/')
@login_required
def painel_diario():
    hoje_str = date.today().isoformat()
    conn = get_db_connection()
    pacientes_ativos_raw = conn.execute("SELECT * FROM pacientes WHERE status = 'Ativo' ORDER BY unidade, leito").fetchall()
    atendimentos_hoje_raw = conn.execute("SELECT * FROM atendimentos WHERE data = ?", (hoje_str,)).fetchall()
    atendimentos_hoje = { p['paciente_id']: {'manha': p['turno_manha'], 'tarde': p['turno_tarde']} for p in atendimentos_hoje_raw }
    conn.close()
    painel = {}
    for p_raw in pacientes_ativos_raw:
        p = dict(p_raw)
        unidade = p['unidade']
        if unidade not in painel: painel[unidade] = []
        p['atendimentos_hoje'] = atendimentos_hoje.get(p['id'], {'manha': False, 'tarde': False})
        painel[unidade].append(p)
    return render_template('painel_diario.html', painel=painel, hoje=hoje_str)

@app.route('/paciente/<int:paciente_id>')
@login_required
def detalhes_paciente(paciente_id):
    conn = get_db_connection()
    paciente = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
    evolucoes = conn.execute("SELECT * FROM evolucoes WHERE paciente_id = ? ORDER BY id DESC", (paciente_id,)).fetchall()
    conn.close()
    if paciente is None: return "Paciente não encontrado", 404
    return render_template('paciente.html', paciente=paciente, evolucoes=evolucoes)

@app.route('/adicionar_evolucao/<int:paciente_id>', methods=['POST'])
@login_required
def adicionar_evolucao(paciente_id):
    conn = get_db_connection()
    agora_str = datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO evolucoes (paciente_id, data, fisio, texto) VALUES (?, ?, ?, ?)",
        (paciente_id, agora_str, current_user.nome_completo, request.form['evolucao'])
    )
    hoje_str, turno = date.today().isoformat(), request.form['turno_atendimento']
    coluna_turno = 'turno_manha' if turno == 'manha' else 'turno_tarde'
    atendimento_existente = conn.execute("SELECT id FROM atendimentos WHERE paciente_id = ? AND data = ?", (paciente_id, hoje_str)).fetchone()
    if atendimento_existente:
        conn.execute(f"UPDATE atendimentos SET {coluna_turno} = 1 WHERE id = ?", (atendimento_existente['id'],))
    else:
        conn.execute(f"INSERT INTO atendimentos (paciente_id, data, {coluna_turno}) VALUES (?, ?, 1)",(paciente_id, hoje_str))
    conn.commit(); conn.close()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

@app.route('/adicionar_paciente')
@login_required
def adicionar_paciente():
    return render_template('form_paciente.html')

@app.route('/salvar_paciente', methods=['POST'])
@login_required
def salvar_paciente():
    conn = get_db_connection()
    conn.execute("INSERT INTO pacientes (nome, idade, leito, unidade, diagnostico) VALUES (?, ?, ?, ?, ?)",
                 (request.form['nome'], request.form['idade'], request.form['leito'], request.form['unidade'], request.form['diagnostico']))
    conn.commit(); conn.close()
    return redirect(url_for('painel_diario'))

@app.route('/paciente/editar/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(paciente_id):
    conn = get_db_connection()
    paciente = conn.execute('SELECT * FROM pacientes WHERE id = ?', (paciente_id,)).fetchone()
    if not paciente:
        flash('Paciente não encontrado.', 'error'); conn.close(); return redirect(url_for('painel_diario'))
    if request.method == 'POST':
        conn.execute('UPDATE pacientes SET nome = ?, idade = ?, leito = ?, unidade = ?, diagnostico = ? WHERE id = ?',
                     (request.form['nome'], request.form['idade'], request.form['leito'], request.form['unidade'], request.form['diagnostico'], paciente_id))
        conn.commit()
        flash('Dados do paciente atualizados com sucesso!', 'success')
    conn.close()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id)) if request.method == 'POST' else render_template('form_paciente.html', paciente=paciente)

@app.route('/marcar_atendimento', methods=['POST'])
@login_required
def marcar_atendimento():
    paciente_id, data_atendimento, turno = int(request.form['paciente_id']), request.form['data'], request.form['turno']
    coluna_turno = 'turno_manha' if turno == 'manha' else 'turno_tarde'
    conn = get_db_connection()
    atendimento_existente = conn.execute("SELECT * FROM atendimentos WHERE paciente_id = ? AND data = ?", (paciente_id, data_atendimento)).fetchone()
    if atendimento_existente:
        status_atual = atendimento_existente[coluna_turno]
        conn.execute(f"UPDATE atendimentos SET {coluna_turno} = ? WHERE id = ?", (1 - status_atual, atendimento_existente['id']))
    else:
        conn.execute(f"INSERT INTO atendimentos (paciente_id, data, {coluna_turno}) VALUES (?, ?, 1)", (paciente_id, data_atendimento))
    conn.commit(); conn.close()
    return redirect(url_for('painel_diario'))

@app.route('/mudar_unidade/<int:paciente_id>', methods=['POST'])
@login_required
def mudar_unidade(paciente_id):
    conn = get_db_connection(); conn.execute("UPDATE pacientes SET unidade = ? WHERE id = ?", (request.form['unidade'], paciente_id)); conn.commit(); conn.close()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

@app.route('/inativar_paciente/<int:paciente_id>', methods=['POST'])
@login_required
def inativar_paciente(paciente_id):
    conn = get_db_connection(); conn.execute("UPDATE pacientes SET status = 'Inativo', motivo_inativacao = ? WHERE id = ?", (request.form['motivo'], paciente_id)); conn.commit(); conn.close()
    return redirect(url_for('painel_diario'))

# --- ROTAS DA ÁREA DO ADMINISTRADOR ---
@app.route('/admin/usuarios')
@login_required
@admin_required
def lista_usuarios():
    conn = get_db_connection(); usuarios = conn.execute('SELECT id, nome_completo, email, funcao, status FROM usuarios ORDER BY nome_completo').fetchall(); conn.close()
    return render_template('admin/lista_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_usuario():
    if request.method == 'POST':
        nome, email, senha, funcao = request.form['nome_completo'], request.form['email'], request.form['senha'], request.form['funcao']
        conn = get_db_connection()
        if conn.execute('SELECT id FROM usuarios WHERE email = ?', (email,)).fetchone():
            flash('Este email já está cadastrado no sistema.', 'error'); conn.close(); return redirect(url_for('criar_usuario'))
        senha_hashed = generate_password_hash(senha)
        conn.execute('INSERT INTO usuarios (nome_completo, email, senha_hash, funcao, precisa_trocar_senha) VALUES (?, ?, ?, ?, 1)',
                     (nome, email, senha_hashed, funcao))
        conn.commit(); conn.close()
        flash('Usuário criado com sucesso! O novo usuário deverá trocar a senha no primeiro login.', 'success')
        return redirect(url_for('lista_usuarios'))
    return render_template('admin/form_usuario.html')

@app.route('/admin/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario(usuario_id):
    conn = get_db_connection()
    usuario = conn.execute('SELECT * FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    if not usuario:
        flash('Usuário não encontrado.', 'error'); conn.close(); return redirect(url_for('lista_usuarios'))
    if request.method == 'POST':
        nome, email, funcao = request.form['nome_completo'], request.form['email'], request.form['funcao']
        if conn.execute('SELECT id FROM usuarios WHERE email = ? AND id != ?', (email, usuario_id)).fetchone():
            flash('Este email já está em uso por outro usuário.', 'error'); conn.close(); return render_template('admin/form_usuario.html', usuario=usuario)
        conn.execute('UPDATE usuarios SET nome_completo = ?, email = ?, funcao = ? WHERE id = ?', (nome, email, funcao, usuario_id))
        conn.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        conn.close()
        return redirect(url_for('lista_usuarios'))
    conn.close()
    return render_template('admin/form_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/inativar/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def inativar_usuario(usuario_id):
    if usuario_id == current_user.id:
        flash('Você não pode inativar a si mesmo.', 'error'); return redirect(url_for('lista_usuarios'))
    conn = get_db_connection(); conn.execute("UPDATE usuarios SET status = 'Inativo' WHERE id = ?", (usuario_id,)); conn.commit(); conn.close()
    flash('Usuário inativado com sucesso.', 'success'); return redirect(url_for('lista_usuarios'))

@app.route('/admin/usuarios/reativar/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def reativar_usuario(usuario_id):
    conn = get_db_connection(); conn.execute("UPDATE usuarios SET status = 'Ativo' WHERE id = ?", (usuario_id,)); conn.commit(); conn.close()
    flash('Usuário reativado com sucesso.', 'success'); return redirect(url_for('lista_usuarios'))

@app.route('/admin/usuarios/resetar_senha/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def resetar_senha(usuario_id):
    conn = get_db_connection()
    usuario = conn.execute('SELECT id, nome_completo FROM usuarios WHERE id = ?', (usuario_id,)).fetchone()
    if not usuario:
        flash('Usuário não encontrado.', 'error'); conn.close(); return redirect(url_for('lista_usuarios'))
    if request.method == 'POST':
        nova_senha = request.form['nova_senha']
        if not nova_senha:
            flash('A senha provisória não pode estar em branco.', 'error'); conn.close(); return render_template('admin/reset_senha_form.html', usuario=usuario)
        senha_hashed = generate_password_hash(nova_senha)
        conn.execute('UPDATE usuarios SET senha_hash = ?, precisa_trocar_senha = 1 WHERE id = ?', (senha_hashed, usuario_id))
        conn.commit()
        flash(f"Senha para '{usuario['nome_completo']}' foi resetada com sucesso!", 'success')
        conn.close()
        return redirect(url_for('lista_usuarios'))
    conn.close()
    return render_template('admin/reset_senha_form.html', usuario=usuario)

# --- Execução do Aplicativo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)