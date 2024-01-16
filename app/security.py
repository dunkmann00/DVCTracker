from passlib.context import CryptContext

#
# create a single global instance for your app...
#
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto"
)
