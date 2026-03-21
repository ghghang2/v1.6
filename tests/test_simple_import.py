"""Simple test to check if nbchat imports work"""
import sys

print("sys.path:")
for i, p in enumerate(sys.path):
    print(f"  {i}: {p}")

# Try importing nbchat
try:
    import nbchat
    print(f"nbchat imported from: {nbchat.__file__}")
except ImportError as e:
    print(f"Failed to import nbchat: {e}")
    sys.exit(1)

# Try importing nbchat.ui
try:
    import nbchat.ui
    print(f"nbchat.ui imported from: {nbchat.ui.__file__}")
except ImportError as e:
    print(f"Failed to import nbchat.ui: {e}")
    sys.exit(1)

# Try importing nbchat.ui.chat_builder
try:
    from nbchat.ui import chat_builder
    print(f"nbchat.ui.chat_builder imported from: {chat_builder.__file__}")
except ImportError as e:
    print(f"Failed to import nbchat.ui.chat_builder: {e}")
    sys.exit(1)

def test_imports_work():
    """Test that all imports work"""
    assert hasattr(nbchat, '__file__')
    assert hasattr(nbchat.ui, '__file__')
    assert hasattr(chat_builder, '__file__')