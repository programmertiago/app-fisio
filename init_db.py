# init_db.py
import sqlite3
from werkzeug.security import generate_password_hash

# Define o nome do arquivo do banco de dados
DB_NAME = 'hospital.db'

# Conecta ao banco de dados (o arquivo será criado se não existir)
conn = sqlite3.connect(DB_NAME)

# Cria um "cursor", que é o objeto que executa os comandos SQL
cursor = conn.cursor()

# --- Comandos para apagar as tabelas se elas já existirem ---
# Isso garante que estamos sempre começando com uma estrutura limpa
cursor.execute('DROP TABLE IF EXISTS atendimentos')
cursor.execute('DROP TABLE IF EXISTS evolucoes')
cursor.execute('DROP TABLE IF EXISTS usuarios')
cursor.execute('DROP TABLE IF EXISTS pacientes')


# --- Comandos SQL para criar as novas tabelas ---

# Cria a tabela 'pacientes' (sem alterações)
cursor.execute('''
    CREATE TABLE pacientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        idade INTEGER,
        leito TEXT,
        unidade TEXT NOT NULL,
        diagnostico TEXT,
        status TEXT NOT NULL DEFAULT 'Ativo',
        motivo_inativacao TEXT
    )
''')

# Cria a tabela 'usuarios' (NOVA!)
cursor.execute('''
    CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        funcao TEXT NOT NULL DEFAULT 'fisioterapeuta'
    )
''')

# Cria a tabela 'evolucoes' (sem alterações)
cursor.execute('''
    CREATE TABLE evolucoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        fisio TEXT NOT NULL,
        texto TEXT NOT NULL,
        FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
    )
''')

# Cria a tabela 'atendimentos' (sem alterações)
cursor.execute('''
    CREATE TABLE atendimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_id INTEGER NOT NULL,
        data TEXT NOT NULL,
        turno_manha INTEGER NOT NULL DEFAULT 0,
        turno_tarde INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (paciente_id) REFERENCES pacientes (id),
        UNIQUE(paciente_id, data)
    )
''')

# --- Adiciona dados de exemplo ---

# Adiciona pacientes de exemplo
cursor.execute('''
    INSERT INTO pacientes (nome, idade, leito, unidade, diagnostico) VALUES
    ('José da Silva', 68, '201-A', '2ª Enfermaria', 'DPOC agudizado'),
    ('Maria Oliveira', 75, 'UTI-05', 'UTI', 'Pós-operatório de cirurgia cardíaca')
''')

# Adiciona um usuário administrador de exemplo (NOVO!)
# A senha 'admin123' é transformada em um hash seguro antes de ser guardada.
senha_hashed = generate_password_hash('admin123')
cursor.execute('''
    INSERT INTO usuarios (nome_completo, email, senha_hash, funcao) VALUES
    ('Admin do Sistema', 'admin@fisio.com', ?, 'admin')
''', (senha_hashed,))


# Salva (commit) as alterações no banco de dados
conn.commit()

# Fecha a conexão
conn.close()

print(f"Banco de dados '{DB_NAME}' recriado com sucesso, com a tabela de usuários!")