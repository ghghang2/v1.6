# Plugin Architecture Research

## Summary

This document summarizes research on plugin architectures, with a focus on OpenClaw's implementation and comparison to other systems.

---

## 1. OpenClaw Plugin Architecture

### Core Concepts

OpenClaw implements a plugin architecture with the following key characteristics:

#### Core Stays Lean
- The core Gateway provides the control plane for sessions, channels, tools, and events
- Optional capabilities ship as plugins (extensions)
- Plugins can add tools, skills, and capabilities without bloating the core

#### Plugin Discovery and Loading
- Plugins are discovered via `openclaw.plugin.json` manifest files
- Skills can be shipped within plugins by listing `skills` directories
- Plugins participate in normal skill precedence rules
- Gating via `metadata.openclaw.requires.config` on plugin config entries

#### Plugin Structure
```
plugin/
├── openclaw.plugin.json  # Plugin manifest
├── tools/                # Tool implementations
├── skills/               # Skill definitions (SKILL.md files)
└── ...
```

#### Key Benefits
1. **Modularity**: Core remains lean, features are optional
2. **Extensibility**: Third-party plugins can extend functionality
3. **Security**: Plugins can be gated by environment, config, and binary presence
4. **Isolation**: Plugins run in controlled environments

---

## 2. Current nbchat Tool Implementation

### Architecture

The nbchat tools are currently implemented using an automatic discovery pattern:

```python
# nbchat/tools/__init__.py
for _, module_name, _ in pkgutil.iter_modules([...]):
    module = importlib.import_module(...)
    func = getattr(module, "func", None)
    # Generate schema from function signature
    # Register tool
```

### Tool Registration Pattern
- Each tool is a separate Python file
- Tools expose a `func` callable
- Automatic schema generation from function signatures
- Centralized tool list via `get_tools()`

### Current Structure
```
nbchat/
├── tools/
│   ├── __init__.py       # Discovery and registration
│   ├── browser.py        # Browser tool
│   ├── create_file.py    # File creation tool
│   ├── get_weather.py    # Weather tool
│   ├── run_command.py    # Command execution
│   ├── send_email.py     # Email tool
│   └── ...
```

---

## 3. Plugin Architecture Patterns (Comparison)

### 3.1 Python Plugin Systems

#### Entry Points (setuptools)
- Uses `entry_points` in `setup.py`/`pyproject.toml`
- Dynamic discovery via `importlib.metadata.entry_points()`
- Common in pytest, Flask extensions, Django apps

#### pkgutil-style Discovery
- Similar to nbchat's current approach
- Scans package directory for modules
- Automatic function detection

#### Plugin Registry Pattern
- Central registry for plugin registration
- Plugins register themselves on import
- Allows runtime plugin management

### 3.2 OpenClaw Plugin System

#### Manifest-Based Discovery
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "tools": [...],
  "skills": [...],
  "requires": {
    "bins": ["binary1", "binary2"],
    "env": ["ENV_VAR"],
    "config": ["browser.enabled"]
  }
}
```

#### Skill Gating
- Environment-based filtering
- Binary presence checks
- Config requirement validation
- OS-specific eligibility

#### Multi-Agent Support
- Per-agent skills in workspace
- Shared skills across agents
- Plugin skills load when plugin is enabled

---

## 4. Comparison: nbchat vs OpenClaw

| Aspect | nbchat (Current) | OpenClaw |
|--------|------------------|----------|
| **Discovery** | Package scan + import | Manifest-based |
| **Registration** | Automatic (pkgutil) | Explicit (plugin.json) |
| **Schema** | Auto-generated from signatures | Defined in manifest |
| **Gating** | None | Environment, config, binary checks |
| **Isolation** | None | Plugin boundaries |
| **Multi-agent** | Single agent | Per-agent + shared |
| **Skills** | Not implemented | SKILL.md format |

---

## 5. Recommendations for nbchat

### Short-term (Immediate)

1. **Add Plugin Manifest Support**
   - Create `nbchat.plugin.json` for plugin metadata
   - Define plugin name, version, and capabilities
   - Allow for optional dependencies

2. **Improve Tool Registration**
   - Add explicit `@tool` decorator
   - Support custom schema definitions
   - Add tool metadata (version, author, etc.)

3. **Add Skill System**
   - Implement SKILL.md format
   - Support skill gating (env vars, config)
   - Create skills/ directory structure

### Medium-term (Next Iteration)

1. **Plugin Package Structure**
   ```
   nbchat/
   ├── core/
   ├── tools/
   ├── plugins/
   │   ├── plugin_name/
   │   │   ├── __init__.py
   │   │   ├── plugin.json
   │   │   └── tools/
   │   └── ...
   └── skills/
   ```

2. **Plugin Discovery**
   - Support loading plugins from external directories
   - Implement plugin lifecycle (load, unload, reload)
   - Add plugin dependency resolution

3. **Security Model**
   - Plugin sandboxing
   - Permission-based tool execution
   - Environment isolation

### Long-term (Future)

1. **Plugin Marketplace**
   - Plugin registry/discovery
   - Version management
   - Dependency resolution

2. **Advanced Features**
   - Plugin hot-reloading
   - Plugin configuration UI
   - Plugin testing framework

---

## 6. Implementation Steps

### Step 1: Add Plugin Manifest Format
```python
# nbchat/plugins/__init__.py
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    tools: List[str]
    skills: List[str]
    requires: Optional[dict] = None
```

### Step 2: Add Tool Decorator
```python
# nbchat/core/decorators.py
def tool(name: str, description: str):
    def decorator(func):
        func.tool_name = name
        func.tool_description = description
        return func
    return decorator
```

### Step 3: Implement Plugin Loader
```python
# nbchat/plugins/loader.py
class PluginLoader:
    def __init__(self):
        self.plugins = {}
    
    def load(self, path: str) -> PluginManifest:
        # Load plugin manifest
        # Register tools
        # Return manifest
    
    def unload(self, name: str):
        # Remove plugin tools
```

---

## 7. Research Sources

1. **OpenClaw Documentation** - https://docs.openclaw.ai
   - Plugin architecture overview
   - Skills system design
   - Tool registration patterns

2. **OpenClaw Plugin Documentation** - https://raw.githubusercontent.com/openclaw/openclaw/main/docs/tools/plugin.md
   - Plugin manifest format
   - Discovery and loading rules
   - Security considerations

3. **OpenClaw Skills Documentation** - https://raw.githubusercontent.com/openclaw/openclaw/main/docs/tools/skills.md
   - Skill format (SKILL.md)
   - Gating mechanisms
   - Multi-agent support

4. **Python Entry Points** - https://docs.python.org/3/library/importlib.html
   - Plugin discovery patterns
   - Dynamic module loading
   - Metadata management

5. **Pytest Plugin System** - https://docs.pytest.org/en/stable/how-to/writing_plugins.html
   - Hook-based architecture
   - Plugin registration
   - Lifecycle management

---

## 8. Conclusion

The OpenClaw plugin architecture provides a mature model for extensible tool systems. Key takeaways for nbchat:

1. **Manifest-based discovery** provides better control than automatic scanning
2. **Skill gating** allows for environment-aware tool availability
3. **Plugin boundaries** enable safer third-party extensions
4. **Multi-agent support** prepares for future scaling

The current nbchat implementation is a good foundation, but adopting plugin concepts from OpenClaw will enable:
- Better organization of tools
- Support for third-party extensions
- Environment-aware tool availability
- Improved security through isolation

---

*Generated by nbchat research assistant*
*Date: 2024*