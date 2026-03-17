import mysql.connector
import bcrypt

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="2004",
    database="prueba1"
)
cursor = conn.cursor()

# Definir credenciales
usuario = "Brayam"
password = "12345"
hash_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Insertar (asegúrate de que el rol_id exista, por ejemplo 1 para Técnico)
cursor.execute("""
    INSERT INTO usuarios (nombre_usuario, contrasena_hash, nombre_completo, email, rol_id)
    VALUES (%s, %s, %s, %s, %s)
""", (usuario, hash_pw, "Brayam", "Brayam@stihl.com", 4))

conn.commit()
cursor.close()
conn.close()
print("Usuario insertado correctamente.")