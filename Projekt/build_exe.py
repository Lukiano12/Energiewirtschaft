"""
Build-Skript für die Merit-Order Visualisierung.
Version: Ohne Fiona-Abhängigkeit
"""
import PyInstaller.__main__
import shutil
import os
from pathlib import Path

APP_NAME = "MeritOrderTool"
ENTRY_POINT = r"src\run.py" 
SOURCE_RESOURCES = r"src\geodata_merit_order\resources"

def build():
    print("=" * 60)
    print(f"  STARTE BUILD: {APP_NAME}")
    print("=" * 60)
    
    # Alte Spec löschen
    if os.path.exists(f"{APP_NAME}.spec"):
        os.remove(f"{APP_NAME}.spec")

    PyInstaller.__main__.run([
        ENTRY_POINT,
        f'--name={APP_NAME}',
        '--onefile',
        '--console',
        '--clean',
        
        # Metadata
        '--copy-metadata=imageio',
        '--copy-metadata=tqdm',
        '--copy-metadata=scipy', 
        
        # Hidden Imports (OHNE Fiona!)
        '--hidden-import=pandas',
        '--hidden-import=numpy',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.pyplot',
        '--hidden-import=matplotlib.backends.backend_tkagg',
        '--hidden-import=openpyxl',
        '--hidden-import=tqdm',
        '--hidden-import=PIL',
        '--hidden-import=geopandas',
        '--hidden-import=shapely',
        '--hidden-import=shapely.geometry',
        '--hidden-import=tkinter',
        '--hidden-import=imageio',
        '--hidden-import=json',
        
        # Collect
        '--collect-all=shapely',
        '--collect-all=geopandas',
        '--collect-all=geodata_merit_order',
        
        '--paths=src',
    ])

    # Check & Copy
    dist_dir = Path("dist")
    exe_path = dist_dir / f"{APP_NAME}.exe"
    
    if not exe_path.exists():
        print("❌ Build fehlgeschlagen.")
        return

    print("✅ EXE erstellt.")
    
    # Resources kopieren
    target_resources = dist_dir / "resources"
    if target_resources.exists(): 
        shutil.rmtree(target_resources)
    
    if os.path.exists(SOURCE_RESOURCES):
        shutil.copytree(SOURCE_RESOURCES, target_resources)
        print("✅ Resources kopiert.")
        
    # Output Ordner
    (dist_dir / "output").mkdir(exist_ok=True)
    
    print("\n" + "=" * 60)
    print("  BUILD ERFOLGREICH!")
    print("=" * 60)

if __name__ == "__main__":
    build()