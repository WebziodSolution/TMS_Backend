import datetime
import random
import string
import jwt
from fastapi import HTTPException
from schemas.user import UserRegister, SetPasswordReq, UserLogin, VerifyOTPReq
from core.security import verify_password, get_password_hash, create_access_token, SECRET_KEY, ALGORITHM
from services.email_service import EmailService
import os

settings_site_url = os.getenv("SITE_URL")

class AuthService:
    @staticmethod
    def register_user(user: UserRegister, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email=%s", (user.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            
            role_id = 1
            sql = "INSERT INTO users (first_name, last_name, email, role_id) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (user.first_name, user.last_name, user.email, role_id))
            db.commit()
            user_id = cursor.lastrowid
            
            token_payload = {"id": user_id, "email": user.email}
            token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)
            
            subject = "Set Your TMS Password"
            context = {
                "subject": subject,
                "title": "Welcome to TMS!",
                "message": "We are excited to have you on board. Please set your password to activate your account.",
                "action_link": f"{settings_site_url}/set-password?token={token}",
                "action_text": "Set Password"
            }
            # EmailService.send_email(user.email, subject, "email_template.html", context)
            
        return {"message": "Registration successful. Please check your email to set a password."}

    @staticmethod
    def set_password(req: SetPasswordReq, db):
        try:
            payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("id")
            email = payload.get("email")
            if not user_id or not email:
                raise HTTPException(status_code=400, detail="Invalid token payload")
        except jwt.PyJWTError:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        with db.cursor() as cursor:
            cursor.execute("SELECT id, is_active FROM users WHERE id=%s AND email=%s", (user_id, email))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="Invalid token/email")
                
            # hashed_password = get_password_hash(req.new_password)
            sql = "UPDATE users SET password_hash=%s, is_active=True WHERE id=%s"
            cursor.execute(sql, (req.new_password, user_id))
            db.commit()
        return {"message": "Password set successfully. You can now login."}

    @staticmethod
    def login(req: UserLogin, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, role_id, first_name, last_name, password_hash, is_active FROM users WHERE email=%s AND password_hash=%s", (req.email, req.password))
            user = cursor.fetchone()
            if not user or not user.get('password_hash'):
                return {"data": None, "message": "Invalid credentials", "status": 400}
                
            if not user['is_active']:
                return {"data": None, "message": "Account not active", "status": 400}
                
            # if not verify_password(req.password, user['password_hash']):
            #     return {"data": None, "message": "Invalid credentials", "status": 400}
                
            # Build permissions object
            cursor.execute("SELECT name FROM roles WHERE id=%s", (user['role_id'],))
            role_record = cursor.fetchone()
            role_name = role_record['name'] if role_record else ""

            cursor.execute(
                """
                SELECT ma.module_id, ma.action_id
                FROM role_module_actions rma
                JOIN modules_actions ma ON rma.module_action_id = ma.id
                WHERE rma.role_id = %s
                """,
                (user['role_id'],)
            )
            role_assigned = cursor.fetchall()

            role_action_map = {}
            for ra in role_assigned:
                mid = ra["module_id"]
                if mid not in role_action_map:
                    role_action_map[mid] = []
                role_action_map[mid].append(ra["action_id"])

            cursor.execute("SELECT id, name FROM functionalities")
            funcs = cursor.fetchall()
            
            cursor.execute("SELECT id, functionality_id, name FROM modules")
            all_modules = cursor.fetchall()

            db.commit()

            functionalities_data = []
            for f in funcs:
                f_mods = []
                for m in [mod for mod in all_modules if mod['functionality_id'] == f['id']]:
                    assigned_actions = role_action_map.get(m['id'], [])
                    f_mods.append({
                        "moduleName": m['name'],
                        "roleAssignedActions": assigned_actions
                    })
                functionalities_data.append({
                    "functionalityName": f['name'],
                    "modules": f_mods
                })
                
            user_data = {
                "rolename": role_name,
                "permissions": {"functionalities": functionalities_data},
                "firstName": user['first_name'],
                "lastName": user['last_name'],
                "id":user['id']
            }

            token = create_access_token({"sub": req.email, "role_id": user['role_id'], "user_id": user['id']})
            
        return {
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "user_details": user_data
            },
            "message": "Login successful"
        }

    @staticmethod
    def verify_otp(req: VerifyOTPReq, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, role_id , first_name , last_name FROM users WHERE email=%s", (req.email,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            sql = "SELECT id FROM otps WHERE user_id=%s AND code=%s AND is_used=False AND expires_at > NOW()"
            cursor.execute(sql, (user['id'], req.otp))
            otp_record = cursor.fetchone()
            
            if not otp_record:
                raise HTTPException(status_code=400, detail="Invalid or expired OTP")
                
            cursor.execute("UPDATE otps SET is_used=True WHERE id=%s", (otp_record['id'],))
            
            # Build permissions object
            cursor.execute("SELECT name FROM roles WHERE id=%s", (user['role_id'],))
            role_record = cursor.fetchone()
            role_name = role_record['name'] if role_record else ""

            cursor.execute(
                """
                SELECT ma.module_id, ma.action_id
                FROM role_module_actions rma
                JOIN modules_actions ma ON rma.module_action_id = ma.id
                WHERE rma.role_id = %s
                """,
                (user['role_id'],)
            )
            role_assigned = cursor.fetchall()

            role_action_map = {}
            for ra in role_assigned:
                mid = ra["module_id"]
                if mid not in role_action_map:
                    role_action_map[mid] = []
                role_action_map[mid].append(ra["action_id"])

            cursor.execute("SELECT id, name FROM functionalities")
            funcs = cursor.fetchall()
            
            cursor.execute("SELECT id, functionality_id, name FROM modules")
            all_modules = cursor.fetchall()

            db.commit()

            functionalities_data = []
            for f in funcs:
                f_mods = []
                for m in [mod for mod in all_modules if mod['functionality_id'] == f['id']]:
                    assigned_actions = role_action_map.get(m['id'], [])
                    f_mods.append({
                        "moduleName": m['name'],
                        "roleAssignedActions": assigned_actions
                    })
                functionalities_data.append({
                    "functionalityName": f['name'],
                    "modules": f_mods
                })
                
            user_data = {
                "rolename": role_name,
                "subUser": False,
                "permissions": {"functionalities": functionalities_data},
                "firstName": user['first_name'],
                "lastName": user['last_name'],
            }

            token = create_access_token({"sub": req.email, "role_id": user['role_id'], "user_id": user['id']})
            
        return {
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "user_details": user_data
            },
            "message": "Login successful"
        }

    @staticmethod
    def forgot_password(email: str, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()
            if user:
                user_id = user['id']
                token_payload = {"id": user_id, "email": email}
                token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)
                
                subject = "Reset Your TMS Password"
                context = {
                    "subject": subject,
                    "title": "Password Reset Request",
                    "message": "We received a request to reset your password. If you didn't make this request, you can safely ignore this email.",
                    "action_link": f"{settings_site_url}/set-password?v={token}",
                    "action_text": "Reset Password"
                }
                # EmailService.send_email(email, subject, "email_template.html", context)
            else:
                return {"status":404,"message": f"{email} is not registered"}
                # raise HTTPException(status_code=404, detail=f"{email} is not registered")
        return {"status":200,"message": "If that email exists, a reset link has been sent."}

    @staticmethod
    def verify_token(token: str, db):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("id")
            email = payload.get("email")
            if not user_id or not email:
                raise HTTPException(status_code=400, detail="Invalid token payload")
        except jwt.PyJWTError:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
            
        with db.cursor() as cursor:
            cursor.execute("SELECT id, email, is_active FROM users WHERE id=%s AND email=%s", (user_id, email))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
        return {"message": "Token is valid", "user": {"id": user_id, "email": email}}