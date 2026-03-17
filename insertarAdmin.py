import mysql.connector
import bcrypt

conn = mysql.connector.connect(host="localhost", user="root", password="2004", database="prueba1")
cursor = conn.cursor()

hash_pw = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

cursor.execute("UPDATE usuarios SET contrasena_hash = %s WHERE nombre_usuario = 'admin'", (hash_pw,))
conn.commit()
cursor.close()
conn.close()
print("Contraseña actualizada con bcrypt.")