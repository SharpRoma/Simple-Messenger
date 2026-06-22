from pydantic import BaseModel

class UserRegister(BaseModel):
    username: str
    password: str
    secret: str

class UserLogin(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserReset(BaseModel):
    username: str
    secret: str
    new_password: str