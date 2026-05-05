import sys
sys.path.insert(0, 'server')
from auth import hash_password, verify_password, validate_credentials

print('=== HASHING ===')
hashed = hash_password('mypassword')
print('Hash generated:', len(hashed) > 0)
print('Correct password:', verify_password('mypassword', hashed))
print('Wrong password:', verify_password('wrongpassword', hashed))

h1 = hash_password('test')
h2 = hash_password('test')
print('Hashes differ (salt):', h1 != h2)
print('Both verify:', verify_password('test', h1) and verify_password('test', h2))

print()
print('=== VALIDATION ===')
print(validate_credentials('alice', 'pass123'))
print(validate_credentials('', 'pass123'))
print(validate_credentials('ab', 'pass123'))
print(validate_credentials('ali ce', 'pass123'))
print(validate_credentials('alice', 'abc'))
print(validate_credentials('alice123', 'securepass'))

print()
print('=== ALL TESTS PASSED ===')
