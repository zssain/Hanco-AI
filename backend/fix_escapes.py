"""Fix escaped characters in pricing.py"""

with open(r'app\api\v1\pricing.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace escaped quotes
content = content.replace(r'\"', '"')

with open(r'app\api\v1\pricing.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed all escaped quotes")
