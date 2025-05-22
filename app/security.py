from nacl import exceptions as nacl_exceptions
from nacl import pwhash

_hasher = pwhash.argon2id
UTF_8 = "utf-8"


def generate_password_hash(password):
    return _hasher.str(password.encode(UTF_8)).decode(UTF_8)


def check_and_update_password_hash(password_hash, password):
    try:
        res = _hasher.verify(
            password_hash.encode(UTF_8), password.encode(UTF_8)
        )
    except nacl_exceptions.CryptoError:
        return False, None
    updated_hash = None
    if not password_hash.startswith(_hasher.STRPREFIX.decode(UTF_8)):
        updated_hash = _hasher.str(password.encode(UTF_8)).decode(UTF_8)
    return True, updated_hash
