import sys, os
sys.path.insert(0, 'server')
from database import DatabaseManager

db = DatabaseManager('test.db')

print('=== USERS ===')
print(db.create_user('alice', 'pass123'))
print(db.create_user('bob', 'pass456'))
print(db.create_user('alice', 'pass123'))
print(db.user_exists('alice'))
print(db.user_exists('ghost'))

print()
print('=== AUTH ===')
print(db.authenticate_user('alice', 'pass123'))
print(db.authenticate_user('alice', 'wrong'))
print(db.authenticate_user('ghost', 'pass123'))

print()
print('=== MESSAGES ===')
mid = db.store_message('alice', 'bob', 'Hello', 'How are you?')
print('Stored ID:', mid)
print(db.store_message('alice', 'nobody', 'Hi', 'test'))

print()
print('=== INBOX ===')
msgs = db.get_messages_for_user('bob')
print('Bob inbox count:', len(msgs))
print('Unread:', msgs[0]['read'])

print()
print('=== RETRIEVE ===')
msg = db.get_message(mid, 'bob')
print('Subject:', msg['subject'])
print('Now read:', msg['read'])
print('Wrong user:', db.get_message(mid, 'alice'))

print()
print('=== DELETE ===')
print(db.delete_message(mid, 'alice'))
print(db.delete_message(mid, 'bob'))
print(db.get_messages_for_user('bob'))

os.remove('test.db')
print()
print('=== ALL TESTS PASSED ===')
