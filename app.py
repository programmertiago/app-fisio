# app.py (versão 100% completa e revisada)

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime
from functools import wraps
import pytz

# Extensões
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user


# --- Configuração Inicial do Aplicativo e Extensões ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-trocar-depois'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = 'hospital.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, DB_NAME)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- Modelos de Banco de Dados (Classes SQLAlchemy) ---
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    funcao = db.Column(db.String(20), nullable=False, default='fisioterapeuta')
    status = db.Column(db.String(20), nullable=False, default='Ativo')
    precisa_trocar_senha = db.Column(db.Boolean, nullable=False, default=False)

class Paciente(db.Model):
    __tablename__ = 'pacientes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    idade = db.Column(db.Integer, nullable=True)
    leito = db.Column(db.String(20))
    unidade = db.Column(db.String(50), nullable=False)
    diagnostico = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Ativo')
    motivo_inativacao = db.Column(db.String(100))
    data_nascimento = db.Column(db.String(10), nullable=False)
    evolucoes = db.relationship('Evolucao', backref='paciente', lazy='dynamic', cascade="all, delete-orphan")
    atendimentos = db.relationship('Atendimento', backref='paciente', lazy='dynamic', cascade="all, delete-orphan")

class Evolucao(db.Model):
    __tablename__ = 'evolucoes'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False)
    fisio = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)

class Atendimento(db.Model):
    __tablename__ = 'atendimentos'
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10), nullable=False)
    turno_manha = db.Column(db.Boolean, nullable=False, default=False)
    turno_tarde = db.Column(db.Boolean, nullable=False, default=False)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('paciente_id', 'data', name='_paciente_data_uc'),)


# --- Funções de Ajuda, Login e Hooks ---
def calcular_idade(data_nascimento_str):
    if not data_nascimento_str: return None
    try:
        hoje = date.today()
        nascimento = datetime.strptime(data_nascimento_str, '%d/%m/%Y').date()
        return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
    except (ValueError, TypeError):
        return None

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.funcao != 'admin':
            flash('Acesso negado.', 'error'); return redirect(url_for('painel_diario'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_force_password_change():
    if current_user.is_authenticated and request.endpoint not in ['logout', 'alterar_senha', 'static']:
        if getattr(current_user, 'precisa_trocar_senha', False):
            flash('Por segurança, você precisa definir uma nova senha.', 'warning'); return redirect(url_for('alterar_senha'))


# --- ROTAS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = Usuario.query.filter_by(email=request.form['email'], status='Ativo').first()
        if usuario and check_password_hash(usuario.senha_hash, request.form['senha']):
            login_user(usuario); return redirect(url_for('painel_diario'))
        else:
            flash('Email ou senha inválidos, ou usuário inativo.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('login'))

@app.route('/alterar-senha', methods=['GET', 'POST'])
@login_required
def alterar_senha():
    if request.method == 'POST':
        senha_atual, nova_senha, confirmacao = request.form['senha_atual'], request.form['nova_senha'], request.form['confirmacao_senha']
        if not check_password_hash(current_user.senha_hash, senha_atual):
            flash('Sua senha atual está incorreta.', 'error')
        elif nova_senha != confirmacao:
            flash('A nova senha e a confirmação não correspondem.', 'error')
        else:
            usuario = db.session.get(Usuario, current_user.id)
            usuario.senha_hash = generate_password_hash(nova_senha)
            usuario.precisa_trocar_senha = False
            db.session.commit()
            flash('Sua senha foi alterada com sucesso!', 'success')
            return redirect(url_for('painel_diario'))
    return render_template('alterar_senha.html')

@app.route('/')
@login_required
def painel_diario():
    hoje_str = date.today().strftime('%d/%m/%Y')
    pacientes_ativos = Paciente.query.filter_by(status='Ativo').order_by(Paciente.unidade, Paciente.leito).all()
    painel = {}
    for p in pacientes_ativos:
        unidade = p.unidade
        if unidade not in painel: painel[unidade] = []
        atendimento_hoje = Atendimento.query.filter_by(paciente_id=p.id, data=date.today().isoformat()).first()
        p.atendimentos_hoje = {'manha': atendimento_hoje.turno_manha if atendimento_hoje else False, 'tarde': atendimento_hoje.turno_tarde if atendimento_hoje else False}
        painel[unidade].append(p)
    return render_template('painel_diario.html', painel=painel, hoje=hoje_str)

@app.route('/arquivo')
@login_required
def arquivo():
    termo_busca = request.args.get('busca', '')
    pacientes_inativos = []
    if termo_busca:
        termo_like = f"%{termo_busca}%"
        pacientes_inativos = Paciente.query.filter(Paciente.status == 'Inativo', Paciente.nome.like(termo_like)).all()
    return render_template('arquivo.html', pacientes=pacientes_inativos, busca=termo_busca)

@app.route('/paciente/<int:paciente_id>')
@login_required
def detalhes_paciente(paciente_id):
    paciente = db.get_or_404(Paciente, paciente_id)
    evolucoes = paciente.evolucoes.order_by(Evolucao.data.desc()).all()
    return render_template('paciente.html', paciente=paciente, evolucoes=evolucoes)

@app.route('/adicionar_evolucao/<int:paciente_id>', methods=['POST'])
@login_required
def adicionar_evolucao(paciente_id):
    paciente = db.get_or_404(Paciente, paciente_id)
    hora_correta = datetime.now(pytz.timezone("America/Sao_Paulo"))
    nova_evolucao = Evolucao(data=hora_correta, fisio=current_user.nome_completo, texto=request.form['evolucao'], paciente_id=paciente.id)
    db.session.add(nova_evolucao)
    hoje_str, turno = date.today().isoformat(), request.form['turno_atendimento']
    atendimento = Atendimento.query.filter_by(paciente_id=paciente_id, data=hoje_str).first()
    if not atendimento:
        atendimento = Atendimento(paciente_id=paciente_id, data=hoje_str)
        db.session.add(atendimento)
    if turno == 'manha': atendimento.turno_manha = True
    else: atendimento.turno_tarde = True
    db.session.commit()
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

@app.route('/adicionar_paciente')
@login_required
def adicionar_paciente():
    return render_template('form_paciente.html', paciente=None)

@app.route('/salvar_paciente', methods=['POST'])
@login_required
def salvar_paciente():
    nome, data_nasc, unidade, leito, diagnostico = request.form['nome'], request.form['data_nascimento'], request.form['unidade'], request.form['leito'], request.form['diagnostico']
    if not data_nasc:
        flash('A data de nascimento é um campo obrigatório.', 'error'); return redirect(url_for('adicionar_paciente'))
    idade_calculada = calcular_idade(data_nasc)
    leito_ocupado = Paciente.query.filter_by(unidade=unidade, leito=leito, status='Ativo').first()
    if leito_ocupado:
        flash(f"Erro: O leito {leito} na {unidade} já está ocupado.", 'error'); return redirect(url_for('adicionar_paciente'))
    paciente_existente = Paciente.query.filter_by(nome=nome, data_nascimento=data_nasc).first()
    if paciente_existente and paciente_existente.status == 'Inativo':
        paciente_existente.status = 'Ativo'; paciente_existente.motivo_inativacao = None; paciente_existente.idade = idade_calculada
        paciente_existente.leito = leito; paciente_existente.unidade = unidade; paciente_existente.diagnostico = diagnostico
        flash(f"Paciente '{nome}' foi REATIVADO com sucesso.", 'success')
    elif paciente_existente:
        flash(f"Erro: Paciente '{nome}' (nascido em {data_nasc}) já está ATIVO.", 'error')
    else:
        novo_paciente = Paciente(nome=nome, idade=idade_calculada, leito=leito, unidade=unidade, diagnostico=diagnostico, data_nascimento=data_nasc)
        db.session.add(novo_paciente); flash(f"Paciente '{nome}' cadastrado com sucesso!", 'success')
    db.session.commit(); return redirect(url_for('painel_diario'))

@app.route('/paciente/editar/<int:paciente_id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(paciente_id):
    paciente = db.get_or_404(Paciente, paciente_id)
    if request.method == 'POST':
        data_nasc = request.form['data_nascimento']
        if not data_nasc:
            flash('A data de nascimento é um campo obrigatório.', 'error'); return render_template('form_paciente.html', paciente=paciente)
        paciente.nome = request.form['nome']; paciente.idade = calcular_idade(data_nasc)
        paciente.leito = request.form['leito']; paciente.unidade = request.form['unidade']
        paciente.diagnostico = request.form['diagnostico']; paciente.data_nascimento = data_nasc
        db.session.commit(); flash('Dados do paciente atualizados com sucesso!', 'success')
        return redirect(url_for('detalhes_paciente', paciente_id=paciente.id))
    return render_template('form_paciente.html', paciente=paciente)

@app.route('/mudar_unidade/<int:paciente_id>', methods=['POST'])
@login_required
def mudar_unidade(paciente_id):
    paciente = db.get_or_404(Paciente, paciente_id)
    nova_unidade = request.form['unidade']
    leito_ocupado = Paciente.query.filter(Paciente.unidade == nova_unidade, Paciente.leito == paciente.leito, Paciente.status == 'Ativo').first()
    if leito_ocupado:
        flash(f"Erro ao transferir: O leito {paciente.leito} na {nova_unidade} já está ocupado.", 'error')
    else:
        paciente.unidade = nova_unidade; db.session.commit(); flash('Paciente transferido com sucesso!', 'success')
    return redirect(url_for('detalhes_paciente', paciente_id=paciente_id))

@app.route('/inativar_paciente/<int:paciente_id>', methods=['POST'])
@login_required
def inativar_paciente(paciente_id):
    paciente = db.get_or_404(Paciente, paciente_id)
    paciente.status = 'Inativo'; paciente.motivo_inativacao = request.form['motivo']
    db.session.commit(); flash('Paciente inativado com sucesso.', 'success')
    return redirect(url_for('painel_diario'))

@app.route('/marcar_atendimento', methods=['POST'])
@login_required
def marcar_atendimento():
    paciente_id, data_atendimento, turno = int(request.form['paciente_id']), request.form['data'], request.form['turno']
    atendimento = Atendimento.query.filter_by(paciente_id=paciente_id, data=data_atendimento).first()
    if not atendimento:
        atendimento = Atendimento(paciente_id=paciente_id, data=data_atendimento); db.session.add(atendimento)
    if turno == 'manha': atendimento.turno_manha = not atendimento.turno_manha
    else: atendimento.turno_tarde = not atendimento.turno_tarde
    db.session.commit(); return redirect(url_for('painel_diario'))

# --- ROTAS DA ÁREA DO ADMINISTRADOR ---
@app.route('/admin/usuarios')
@login_required
@admin_required
def lista_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome_completo).all()
    return render_template('admin/lista_usuarios.html', usuarios=usuarios)

@app.route('/admin/usuarios/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def criar_usuario():
    if request.method == 'POST':
        nome, email, senha, funcao = request.form['nome_completo'], request.form['email'], request.form['senha'], request.form['funcao']
        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está cadastrado.', 'error'); return redirect(url_for('criar_usuario'))
        novo_usuario = Usuario(nome_completo=nome, email=email, senha_hash=generate_password_hash(senha), funcao=funcao, precisa_trocar_senha=True)
        db.session.add(novo_usuario); db.session.commit(); flash('Usuário criado com sucesso!', 'success'); return redirect(url_for('lista_usuarios'))
    return render_template('admin/form_usuario.html', usuario=None)

@app.route('/admin/usuarios/editar/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_usuario_admin(usuario_id):
    # Busca o usuário pelo ID ou retorna um erro 404 se não encontrar
    usuario = db.get_or_404(Usuario, usuario_id)

    if request.method == 'POST':
        # Coleta os novos dados do formulário
        novo_email = request.form['email']
        
        # Verifica se o novo email já não está em uso por OUTRO usuário
        usuario_existente = Usuario.query.filter(Usuario.email == novo_email, Usuario.id != usuario_id).first()
        if usuario_existente:
            flash('Este email já está em uso por outro usuário.', 'error')
            # Retorna para o formulário de edição sem salvar
            return render_template('admin/form_usuario.html', usuario=usuario)

        # Se tudo estiver ok, atualiza os dados
        usuario.nome_completo = request.form['nome_completo']
        usuario.email = novo_email
        usuario.funcao = request.form['funcao']
        
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('lista_usuarios'))
    
    # Para requisições GET, apenas mostra o formulário pré-preenchido
    return render_template('admin/form_usuario.html', usuario=usuario)

@app.route('/admin/usuarios/inativar/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def inativar_usuario_admin(usuario_id):
    if usuario_id == current_user.id:
        flash('Você não pode inativar a si mesmo.', 'error')
        return redirect(url_for('lista_usuarios'))

    usuario = db.session.get(Usuario, usuario_id)
    if usuario:
        usuario.status = 'Inativo'
        db.session.commit()
        flash('Usuário inativado com sucesso.', 'success')
    return redirect(url_for('lista_usuarios'))

@app.route('/admin/usuarios/reativar/<int:usuario_id>', methods=['POST'])
@login_required
@admin_required
def reativar_usuario_admin(usuario_id):
    usuario = db.session.get(Usuario, usuario_id)
    if usuario: usuario.status = 'Ativo'; db.session.commit(); flash('Usuário reativado com sucesso.', 'success')
    return redirect(url_for('lista_usuarios'))

@app.route('/admin/usuarios/resetar_senha/<int:usuario_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def resetar_senha_admin(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if request.method == 'POST':
        nova_senha = request.form['nova_senha']
        if not nova_senha: flash('A senha provisória não pode estar em branco.', 'error'); return render_template('admin/reset_senha_form.html', usuario=usuario)
        usuario.senha_hash = generate_password_hash(nova_senha); usuario.precisa_trocar_senha = True
        db.session.commit(); flash(f"Senha para '{usuario.nome_completo}' foi resetada com sucesso!", 'success'); return redirect(url_for('lista_usuarios'))
    return render_template('admin/reset_senha_form.html', usuario=usuario)

# --- Comandos de CLI Personalizados ---
@app.cli.command('create-admin')
def create_admin_command():
    if Usuario.query.filter_by(email='admin@fisio.com').first(): print('O usuário administrador já existe.'); return
    admin_user = Usuario(nome_completo='Admin do Sistema', email='admin@fisio.com', senha_hash=generate_password_hash('admin123'), funcao='admin', status='Ativo')
    db.session.add(admin_user); db.session.commit(); print('Usuário administrador criado com sucesso!')

# --- Execução do Aplicativo ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)