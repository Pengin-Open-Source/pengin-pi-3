from .users import User #required for settings.py AUTH_USER_MODEL = 'main.User'
from .address import Address, AddressHistory
from .slug import Slug, SlugHistory
