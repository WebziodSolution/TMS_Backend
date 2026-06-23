from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr

class SetPasswordReq(BaseModel):
    token: str 
    new_password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class VerifyOTPReq(BaseModel):
    email: EmailStr
    otp: str
