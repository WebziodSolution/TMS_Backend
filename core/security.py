from passlib.context import CryptContext
from fastapi import Header
import jwt

SECRET_KEY = "super_secret_tms_jwt_key_secure_length_32_bytes"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False
    # Try custom decryption if prefixed with enc_
    if hashed_password.startswith("enc_"):
        try:
            import base64
            import hashlib
            encrypted_part = hashed_password[4:]
            data = base64.urlsafe_b64decode(encrypted_part.encode('utf-8'))
            if len(data) >= 16:
                iv = data[:16]
                cipher_bytes = data[16:]
                plain_bytes = bytearray()
                
                block_index = 0
                while len(plain_bytes) < len(cipher_bytes):
                    h = hashlib.sha256(SECRET_KEY.encode('utf-8') + iv + str(block_index).encode('utf-8')).digest()
                    for b in h:
                        if len(plain_bytes) < len(cipher_bytes):
                            plain_bytes.append(cipher_bytes[len(plain_bytes)] ^ b)
                        else:
                            break
                    block_index += 1
                    
                decrypted = plain_bytes.decode('utf-8')
                return plain_password == decrypted
        except Exception:
            pass

    # Fallback to bcrypt verification
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False

def get_password_hash(password):
    return pwd_context.hash(password)

def get_password_encrypted(password):
    import base64
    import hashlib
    import secrets
    iv = secrets.token_bytes(16)
    plain_bytes = password.encode('utf-8')
    cipher_bytes = bytearray()
    
    block_index = 0
    while len(cipher_bytes) < len(plain_bytes):
        h = hashlib.sha256(SECRET_KEY.encode('utf-8') + iv + str(block_index).encode('utf-8')).digest()
        for b in h:
            if len(cipher_bytes) < len(plain_bytes):
                cipher_bytes.append(plain_bytes[len(cipher_bytes)] ^ b)
            else:
                break
        block_index += 1
        
    enc_b64 = base64.urlsafe_b64encode(iv + cipher_bytes).decode('utf-8')
    return f"enc_{enc_b64}"

def decrypt_password(encrypted_password):
    if not encrypted_password:
        return None
    try:
        import base64
        import hashlib
        encrypted_part = encrypted_password[4:]
        data = base64.urlsafe_b64decode(encrypted_part.encode('utf-8'))
        if len(data) >= 16:
            iv = data[:16]
            cipher_bytes = data[16:]
            plain_bytes = bytearray()
            
            block_index = 0
            while len(plain_bytes) < len(cipher_bytes):
                h = hashlib.sha256(SECRET_KEY.encode('utf-8') + iv + str(block_index).encode('utf-8')).digest()
                for b in h:
                    if len(plain_bytes) < len(cipher_bytes):
                        plain_bytes.append(cipher_bytes[len(plain_bytes)] ^ b)
                    else:
                        break
                block_index += 1
                
            return plain_bytes.decode('utf-8')
    except Exception:
        pass
    return None

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_id(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("user_id")
    except jwt.PyJWTError:
        return None
