import sys
import os

# Füge das aktuelle Verzeichnis zum Suchpfad hinzu
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importiere die main-Funktion aus dem Paket
from geodata_merit_order.main import main

if __name__ == "__main__":
    main()