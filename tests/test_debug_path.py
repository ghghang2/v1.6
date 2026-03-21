import sys
print("sys.path during test collection:")
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}")
print()
print("nbchat in sys.modules:", 'nbchat' in sys.modules)
print("nbchat.ui in sys.modules:", 'nbchat.ui' in sys.modules)

def test_debug():
    pass
