# init_db.py
import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = 'hospital.db'
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Apaga as tabelas antigas para garantir uma recriação limpa
cursor.execute('DROP TABLE IF EXISTS atendimentos')
cursor.execute('DROP TABLE IF EXISTS evolucoes')
cursor.execute('DROP TABLE IF EXISTS usuarios')
cursor.execute('DROP TABLE IF EXISTS pacientes')

# Cria a tabela 'pacientes'
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

# Cria a tabela 'usuarios' com a nova coluna 'precisa_trocar_senha'
cursor.execute('''
    CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_completo TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        funcao TEXT NOT NULL DEFAULT 'fisioterapeuta',
        status TEXT NOT NULL DEFAULT 'Ativo',
        precisa_trocar_senha INTEGER NOT NULL DEFAULT 0
    )
''')

# Cria as outras tabelas... (código inalterado)
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

# Adiciona dados de exemplo... (código inalterado)
cursor.execute("INSERT INTO pacientes (nome, idade, leito, unidade, diagnostico) VALUES ('José da Silva', 68, '201-A', '2ª Enfermaria', 'DPOC agudizado')")
senha_hashed = generate_password_hash('admin123')
cursor.execute("INSERT INTO usuarios (nome_completo, email, senha_hash, funcao) VALUES ('Admin do Sistema', 'admin@fisio.com', ?, 'admin')", (senha_hashed,))

conn.commit()
conn.close()

print(f"Banco de dados '{DB_NAME}' recriado com sucesso, com a coluna 'precisa_trocar_senha'!")