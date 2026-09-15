from app.auth.schemas import UserPublic

# Re-exported so `from app.users.schemas import UserPublic` reads naturally
# from within the users module, without duplicating the model definition.
__all__ = ["UserPublic"]
