from core.security import create_access_token
from core.database import SessionLocal
from models import Athlete
db = SessionLocal()
u = db.query(Athlete).filter(Athlete.email == 'mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(u.id), 'email': u.email, 'role': u.role}))
db.close()
