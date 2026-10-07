"""Cria o primeiro gestor pelo terminal, sem dados ficticios nem senha padrao."""
from getpass import getpass

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User
from app.models.enums import UserRole


class FirstAdmin(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)


def main() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role == UserRole.ADMIN)) is not None:
            raise SystemExit("Ja existe um gestor. Crie outros acessos pelo painel.")
        nome = input("Nome do gestor: ").strip()
        email = input("Email: ").strip().lower()
        senha = getpass("Senha (minimo 8 caracteres): ")
        if senha != getpass("Confirme a senha: "):
            raise SystemExit("As senhas nao coincidem.")
        account = FirstAdmin(nome=nome, email=email, senha=senha)
        db.add(User(nome=account.nome, email=str(account.email),
                    senha_hash=get_password_hash(account.senha), role=UserRole.ADMIN, ativo=True))
        db.commit()
        print("Gestor criado. Entre no sistema com o email informado.")


if __name__ == "__main__":
    main()
