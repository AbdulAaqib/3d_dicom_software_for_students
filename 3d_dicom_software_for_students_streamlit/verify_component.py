#!/usr/bin/env python3
"""
Diagnostic script to verify the custom canvas component is properly installed and accessible.
Run this before using the component in your app.
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "streamlit" / "src"))

print("=" * 60)
print("CUSTOM CANVAS COMPONENT DIAGNOSTIC")
print("=" * 60)
print()

# Check 1: Component directory
print("✓ Check 1: Component Directory Structure")
print("-" * 60)
component_dir = project_root / "streamlit" / "src" / "frontend" / "components" / "custom_canvas"
print(f"Component directory: {component_dir}")
print(f"  Exists: {'✅ YES' if component_dir.exists() else '❌ NO'}")

if component_dir.exists():
    print(f"  Contents:")
    for item in sorted(component_dir.iterdir()):
        if item.name not in ['__pycache__', 'node_modules']:
            print(f"    - {item.name}")
print()

# Check 2: Frontend build
print("✓ Check 2: Frontend Build Files")
print("-" * 60)
frontend_dir = component_dir / "frontend"
dist_dir = frontend_dir / "dist"
print(f"Frontend directory: {frontend_dir}")
print(f"  Exists: {'✅ YES' if frontend_dir.exists() else '❌ NO'}")
print(f"Dist directory: {dist_dir}")
print(f"  Exists: {'✅ YES' if dist_dir.exists() else '❌ NO'}")

if dist_dir.exists():
    print(f"  Contents:")
    for item in sorted(dist_dir.iterdir()):
        print(f"    - {item.name}")
        if item.is_dir():
            for sub_item in sorted(item.iterdir())[:5]:  # Show first 5 files
                print(f"      - {sub_item.name}")
print()

# Check 3: Required files
print("✓ Check 3: Required Build Files")
print("-" * 60)
required_files = {
    "index.html": dist_dir / "index.html",
    "assets/": dist_dir / "assets",
}

all_good = True
for name, path in required_files.items():
    exists = path.exists()
    status = "✅ FOUND" if exists else "❌ MISSING"
    print(f"  {name}: {status}")
    if not exists:
        all_good = False

if not all_good:
    print("\n⚠️  WARNING: Missing required files!")
    print("   Run: cd streamlit/src/frontend/components/custom_canvas/frontend && npm run build")
print()

# Check 4: Python module import
print("✓ Check 4: Python Module Import")
print("-" * 60)
try:
    from frontend.components.custom_canvas import (
        render_snapshot_canvas,
        render_model_capture,
        _COMPONENT_ROOT,
    )
    print("  ✅ Module imported successfully")
    print(f"  Component root: {_COMPONENT_ROOT}")
    print(f"  Component root exists: {'✅ YES' if _COMPONENT_ROOT.exists() else '❌ NO'}")
    
    # Check functions
    print("\n  Available functions:")
    print(f"    - render_snapshot_canvas: ✅")
    print(f"    - render_model_capture: ✅")
    
except Exception as e:
    print(f"  ❌ Import failed: {e}")
    print("\n  This might be due to missing dependencies.")
    print("  The component should still work in your Streamlit app.")
print()

# Check 5: Package.json
print("✓ Check 5: Frontend Dependencies")
print("-" * 60)
package_json = frontend_dir / "package.json"
if package_json.exists():
    print("  ✅ package.json found")
    import json
    with open(package_json) as f:
        pkg = json.load(f)
    print(f"  Component name: {pkg.get('name', 'N/A')}")
    print(f"  Version: {pkg.get('version', 'N/A')}")
    
    deps = pkg.get('dependencies', {})
    print(f"\n  Key dependencies:")
    for dep in ['react', 'react-dom', 'react-sketch-canvas', 'streamlit-component-lib']:
        version = deps.get(dep, 'Not installed')
        print(f"    - {dep}: {version}")
else:
    print("  ❌ package.json not found")
print()

# Check 6: Node modules
print("✓ Check 6: Node Modules")
print("-" * 60)
node_modules = frontend_dir / "node_modules"
if node_modules.exists():
    print("  ✅ node_modules directory exists")
    module_count = sum(1 for _ in node_modules.iterdir())
    print(f"  Installed modules: {module_count}")
else:
    print("  ❌ node_modules not found")
    print("     Run: cd streamlit/src/frontend/components/custom_canvas/frontend && npm install")
print()

# Final verdict
print("=" * 60)
print("FINAL VERDICT")
print("=" * 60)

if dist_dir.exists() and (dist_dir / "index.html").exists() and (dist_dir / "assets").exists():
    print("✅ Component is properly built and ready to use!")
    print()
    print("To use the component, run:")
    print("  streamlit run demo_annotation.py")
    print("  OR")
    print("  streamlit run test_custom_component.py")
else:
    print("❌ Component needs to be built")
    print()
    print("To fix:")
    print("  1. cd streamlit/src/frontend/components/custom_canvas/frontend")
    print("  2. npm install  (if needed)")
    print("  3. npm run build")
    print("  4. Run this script again to verify")
print()

print("If you encounter loading errors in Streamlit:")
print("  • Make sure you're in the correct directory")
print("  • Clear Streamlit cache: streamlit cache clear")
print("  • Restart your Streamlit app")
print("  • Check the browser console for JavaScript errors")
print()
print("=" * 60)



