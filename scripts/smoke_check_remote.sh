#!/bin/bash
TOKEN=$(docker exec strideiq_api python -c "
from core.security import create_access_token
from database import SessionLocal
from models import Athlete
db = SessionLocal()
user = db.query(Athlete).filter(Athlete.email=='mbshaf@gmail.com').first()
print(create_access_token(data={'sub': str(user.id), 'email': user.email, 'role': user.role}))
db.close()
")
echo "TOKEN obtained"
curl -s -H "Authorization: Bearer $TOKEN" https://strideiq.run/v1/home | python3 -c 'import json,sys; d=json.load(sys.stdin); print("HOME OK - keys:", list(d.keys())[:5])'
