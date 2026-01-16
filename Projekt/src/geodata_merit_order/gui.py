"""
GUI-Funktionen für die Merit-Order Visualisierung.
Verwendet tkinter für Dialoge.
"""

import tkinter as tk
from tkinter import ttk, messagebox

def scenario_selection(scenario_ids):
    """
    Zeigt ein Auswahlfenster für die Szenarien.
    
    Args:
        scenario_ids: Liste der verfügbaren Szenario-IDs
        
    Returns:
        Ausgewählte Szenario-ID oder None bei Abbruch
    """
    selected = [None]
    
    root = tk.Tk()
    root.title("Merit-Order Visualisierung")
    root.geometry("500x600")
    root.minsize(400, 500)
    
    # Fenster zentrieren
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (500 // 2)
    y = (root.winfo_screenheight() // 2) - (600 // 2)
    root.geometry(f"+{x}+{y}")
    
    # Farben definieren
    bg_color = "#2b2b2b"
    fg_color = "#ffffff"
    accent_color = "#4a9eff"
    btn_color = "#3d3d3d"
    btn_hover = "#4d4d4d"
    
    root.configure(bg=bg_color)
    
    # Hauptframe mit Padding
    main_frame = tk.Frame(root, bg=bg_color, padx=30, pady=20)
    main_frame.pack(fill='both', expand=True)
    
    # Titel
    title_label = tk.Label(
        main_frame, 
        text="⚡ Merit-Order Visualisierung",
        font=("Segoe UI", 18, "bold"),
        bg=bg_color,
        fg=accent_color
    )
    title_label.pack(pady=(10, 5))
    
    # Untertitel
    subtitle_label = tk.Label(
        main_frame, 
        text="Strompreisanalyse für Deutschland",
        font=("Segoe UI", 10),
        bg=bg_color,
        fg="#888888"
    )
    subtitle_label.pack(pady=(0, 20))
    
    # Trennlinie
    separator = tk.Frame(main_frame, height=2, bg="#444444")
    separator.pack(fill='x', pady=10)
    
    # Beschreibung
    desc_label = tk.Label(
        main_frame, 
        text="Wählen Sie ein Szenario für die Visualisierung:",
        font=("Segoe UI", 11),
        bg=bg_color,
        fg=fg_color
    )
    desc_label.pack(pady=(10, 15))
    
    # Szenario-Gruppen
    groups = {
        "🇩🇪 Deutschland": ['de_single'],
        "📍 4 Zonen (ÜNB-Gebiete)": ['z4_insel', 'z4_coupled', 'z4_diff'],
        "🧭 Nord-Süd": ['ns_insel', 'ns_coupled', 'ns_diff']
    }
    
    # Szenario-Beschreibungen
    descriptions = {
        'de_single': 'Deutschland gesamt',
        'z4_insel': 'Inselbetrachtung',
        'z4_coupled': 'Gekoppelt (Handel)',
        'z4_diff': 'Preisdifferenz',
        'ns_insel': 'Inselbetrachtung',
        'ns_coupled': 'Gekoppelt (Handel)',
        'ns_diff': 'Preisdifferenz',
    }
    
    # Icons für Szenariotypen
    icons = {
        'insel': '🏝️',
        'coupled': '🔗',
        'diff': '📊',
        'single': '🗺️'
    }
    
    def get_icon(scenario_id):
        for key, icon in icons.items():
            if key in scenario_id:
                return icon
        return '📌'
    
    def on_select(scenario_id):
        selected[0] = scenario_id
        root.destroy()
    
    def create_button(parent, scenario_id, text):
        icon = get_icon(scenario_id)
        btn_text = f"{icon}  {text}"
        
        btn = tk.Button(
            parent,
            text=btn_text,
            font=("Segoe UI", 11),
            bg=btn_color,
            fg=fg_color,
            activebackground=btn_hover,
            activeforeground=fg_color,
            relief='flat',
            cursor='hand2',
            width=25,
            height=1,
            command=lambda s=scenario_id: on_select(s)
        )
        
        # Hover-Effekte
        def on_enter(e):
            btn.configure(bg=btn_hover)
        def on_leave(e):
            btn.configure(bg=btn_color)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    # Scrollbarer Bereich für Buttons
    button_frame = tk.Frame(main_frame, bg=bg_color)
    button_frame.pack(fill='both', expand=True, pady=10)
    
    for group_name, group_scenarios in groups.items():
        # Gruppen-Label
        group_label = tk.Label(
            button_frame,
            text=group_name,
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg=accent_color,
            anchor='w'
        )
        group_label.pack(fill='x', pady=(15, 8))
        
        # Buttons für diese Gruppe
        for scenario_id in group_scenarios:
            if scenario_id in scenario_ids:
                btn_text = descriptions.get(scenario_id, scenario_id)
                btn = create_button(button_frame, scenario_id, btn_text)
                btn.pack(pady=3)
    
    # Trennlinie vor Beenden
    separator2 = tk.Frame(main_frame, height=2, bg="#444444")
    separator2.pack(fill='x', pady=20)
    
    # Info-Text
    info_text = tk.Label(
        main_frame,
        text="Steuerung in der Visualisierung:\n"
             "← → Stunde wechseln  |  ↑ ↓ Monat wechseln  |  V Video speichern",
        font=("Segoe UI", 9),
        bg=bg_color,
        fg="#666666",
        justify='center'
    )
    info_text.pack(pady=(0, 10))
    
    # Beenden-Button
    exit_btn = tk.Button(
        main_frame,
        text="✖  Beenden",
        font=("Segoe UI", 11),
        bg="#8b0000",
        fg=fg_color,
        activebackground="#a00000",
        activeforeground=fg_color,
        relief='flat',
        cursor='hand2',
        width=20,
        command=root.destroy
    )
    exit_btn.pack(pady=10)
    
    # Escape zum Schließen
    root.bind('<Escape>', lambda e: root.destroy())
    
    # Fenster anpassbar machen
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    
    root.mainloop()
    
    return selected[0]

def ask_save_video():
    """
    Fragt den Benutzer, ob das Video gespeichert werden soll.
    """
    root = tk.Tk()
    root.withdraw()
    
    result = messagebox.askyesno(
        "Video speichern",
        "Möchten Sie die Animation als Video speichern?\n\n"
        "Dies kann einige Minuten dauern.\n"
        "Benötigt: ffmpeg",
        icon='question'
    )
    
    root.destroy()
    return result

def show_error(title, message):
    """Zeigt eine Fehlermeldung an."""
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)
    root.destroy()

def show_info(title, message):
    """Zeigt eine Informationsmeldung an."""
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(title, message)
    root.destroy()