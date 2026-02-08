import sys
import os
import traceback # Wichtig für Fehlerausgabe

# Füge das aktuelle Verzeichnis zum Suchpfad hinzu
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importiere die main-Funktion aus dem Paket
from geodata_merit_order.main import main

if __name__ == "__main__":
    try:
        main()
        # Damit das Fenster offen bleibt, wenn das Programm normal endet:
        input("\nProgramm beendet. Drücken Sie Enter zum Schließen...")
    except Exception:
        # Hier fangen wir JEDEN Fehler ab und zeigen ihn an
        print("\n" + "!"*60)
        print("KRITISCHER FEHLER AUFGETRETEN:")
        print("!"*60 + "\n")
        traceback.print_exc()
        print("\n" + "!"*60)
        input("\nDrücken Sie Enter zum Beenden...")