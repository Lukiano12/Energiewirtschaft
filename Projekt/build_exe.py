"""
Build-Skript für die Merit-Order Visualisierung.
Version: Mit automatischer Ressourcen-Kopie (inkl. FFmpeg)
"""
import PyInstaller.__main__
import shutil
import os
from pathlib import Path

# Pfad-Konfiguration
BASE_DIR = Path(__file__).resolve().parent
APP_NAME = "MeritOrderTool"
ENTRY_POINT = str(BASE_DIR / "src" / "run.py")
SOURCE_RESOURCES = BASE_DIR / "src" / "geodata_merit_order" / "resources"
DIST_DIR = BASE_DIR / "dist"

def build():
    print("=" * 60)
    print(f"  STARTE BUILD: {APP_NAME}")
    print("=" * 60)

    # 1. Vorab-Check für FFmpeg
    ffmpeg_exe = SOURCE_RESOURCES / "ffmpeg.exe"
    if not ffmpeg_exe.exists():
        print(f"⚠️  WARNUNG: ffmpeg.exe nicht in {SOURCE_RESOURCES} gefunden!")
        print("   MP4-Export wird in der fertigen EXE nicht funktionieren.")
        input("   Drücken Sie ENTER um trotzdem fortzufahren oder STRG+C zum Abbrechen...")
    else:
        print("✅ ffmpeg.exe gefunden - wird integriert.")

    # 2. Alte Build-Artefakte löschen
    if (BASE_DIR / f"{APP_NAME}.spec").exists():
        os.remove(BASE_DIR / f"{APP_NAME}.spec")
    
    if (BASE_DIR / "build").exists():
        shutil.rmtree(BASE_DIR / "build")

    # 3. PyInstaller ausführen
    PyInstaller.__main__.run([
        ENTRY_POINT,
        f'--name={APP_NAME}',
        '--onefile',
        '--console',   # <--- ÄNDERUNG: Vorher war hier --noconsole
        '--clean',
        
        # Metadata für Pakete die es brauchen
        '--copy-metadata=imageio',
        '--copy-metadata=tqdm',
        '--copy-metadata=scipy', 
        
        # Hidden Imports (Explizit machen hilft oft)
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
        '--hidden-import=tkinter',
        '--hidden-import=imageio',
        '--hidden-import=imageio_ffmpeg', # Sicherheitshalber
        
        # Geodaten Pakete sammeln
        '--collect-all=shapely',
        '--collect-all=geopandas',
        '--collect-all=geodata_merit_order',
        
        f'--paths={str(BASE_DIR / "src")}',
    ])

    # 4. Ressourcen kopieren (Das "Sidecar" Prinzip)
    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    
    if not exe_path.exists():
        print("❌ Build fehlgeschlagen. Keine EXE erstellt.")
        return

    print("✅ EXE erstellt.")
    
    # Ziel-Ordner vorbereiten
    target_resources = DIST_DIR / "resources"
    
    # Alten Resource Ordner im dist löschen falls vorhanden
    if target_resources.exists(): 
        shutil.rmtree(target_resources)
    
    # Ordner komplett kopieren (inkl. Excels, GeoJSON und ffmpeg.exe)
    if SOURCE_RESOURCES.exists():
        shutil.copytree(SOURCE_RESOURCES, target_resources)
        print(f"✅ Resources kopiert nach: {target_resources}")
    else:
        print(f"❌ Quell-Resources nicht gefunden: {SOURCE_RESOURCES}")

    print("\n" + "=" * 60)
    print("  BUILD ERFOLGREICH!")
    print(f"  Ordner für Weitergabe: {DIST_DIR}")
    print("  (Kopieren Sie den ganzen Inhalt von 'dist', nicht nur die exe!)")
    print("=" * 60)

if __name__ == "__main__":
    build()