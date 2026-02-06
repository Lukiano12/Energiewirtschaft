"""
GUI-Funktionen für die Merit-Order Visualisierung.
Verwendet tkinter für Dialoge.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from . import config

def scenario_selection(scenario_ids):
    """
    Zeigt ein Auswahlfenster für die Szenarien, gruppiert nach Jahr.
    """
    selected = [None]
    
    root = tk.Tk()
    root.title("Merit-Order Visualisierung")
    root.geometry("600x750")
    root.minsize(500, 650)
    
    # Fenster zentrieren
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (600 // 2)
    y = (root.winfo_screenheight() // 2) - (750 // 2)
    root.geometry(f"+{x}+{y}")
    
    # Farben definieren
    bg_color = "#2b2b2b"
    fg_color = "#ffffff"
    accent_color = "#4a9eff"
    btn_color = "#3d3d3d"
    btn_hover = "#4d4d4d"
    year_colors = {
        2024: "#4CAF50",  # Grün
        2037: "#FF9800",  # Orange
        2045: "#E91E63",  # Pink
    }
    
    root.configure(bg=bg_color)
    
    # Hauptframe mit Scrollbar
    main_frame = tk.Frame(root, bg=bg_color)
    main_frame.pack(fill='both', expand=True)
    
    # Canvas für Scrolling
    canvas = tk.Canvas(main_frame, bg=bg_color, highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=bg_color)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Mausrad-Scrolling
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True, padx=20, pady=10)
    
    # Titel
    title_label = tk.Label(
        scrollable_frame, 
        text="⚡ Merit-Order Visualisierung",
        font=("Segoe UI", 18, "bold"),
        bg=bg_color,
        fg=accent_color
    )
    title_label.pack(pady=(10, 5))
    
    # Untertitel
    subtitle_label = tk.Label(
        scrollable_frame, 
        text="Strompreisanalyse für Deutschland",
        font=("Segoe UI", 10),
        bg=bg_color,
        fg="#888888"
    )
    subtitle_label.pack(pady=(0, 15))
    
    def on_select(scenario_id):
        selected[0] = scenario_id
        root.destroy()
    
    def create_button(parent, scenario_id, text, year=None):
        # Icons für Szenariotypen
        if 'epex' in scenario_id:
            icon = '📊'
        elif 'diff' in scenario_id:
            icon = '📈'
        elif 'coupled' in scenario_id:
            icon = '🔗'
        elif 'insel' in scenario_id:
            icon = '🏝️'
        elif 'single' in scenario_id:
            icon = '🗺️'
        else:
            icon = '📌'
        
        btn_text = f"{icon}  {text}"
        
        # Jahr-spezifische Farbe
        btn_bg = btn_color
        if year and year in year_colors:
            btn_bg = year_colors[year]
        
        btn = tk.Button(
            parent,
            text=btn_text,
            font=("Segoe UI", 10),
            bg=btn_bg,
            fg=fg_color,
            activebackground=btn_hover,
            activeforeground=fg_color,
            relief='flat',
            cursor='hand2',
            width=35,
            height=1,
            command=lambda s=scenario_id: on_select(s)
        )
        
        def on_enter(e):
            btn.configure(bg=btn_hover)
        def on_leave(e):
            btn.configure(bg=btn_bg)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    # =========================================================================
    # EPEX-Vergleich (Spezial-Sektion)
    # =========================================================================
    epex_frame = tk.Frame(scrollable_frame, bg=bg_color)
    epex_frame.pack(fill='x', pady=(10, 5))
    
    epex_label = tk.Label(
        epex_frame,
        text="📊 EPEX-Vergleich (Modell vs. Realität)",
        font=("Segoe UI", 12, "bold"),
        bg=bg_color,
        fg="#FFD700",  # Gold
        anchor='w'
    )
    epex_label.pack(fill='x', pady=(5, 8))
    
    if 'epex_comparison_2024' in scenario_ids:
        btn = create_button(epex_frame, 'epex_comparison_2024', 'Modell vs. EPEX Spot 2024')
        btn.configure(bg="#FFD700", fg="#000000")
        btn.pack(pady=3)
    
    # Trennlinie
    separator = tk.Frame(scrollable_frame, height=2, bg="#444444")
    separator.pack(fill='x', pady=15)
    
    # =========================================================================
    # Szenarien nach Jahr gruppiert
    # =========================================================================
    for year in config.AVAILABLE_YEARS:
        year_color = year_colors.get(year, accent_color)
        
        # Jahr-Header
        year_frame = tk.Frame(scrollable_frame, bg=bg_color)
        year_frame.pack(fill='x', pady=(15, 5))
        
        year_label = tk.Label(
            year_frame,
            text=f"📅 Jahr {year}",
            font=("Segoe UI", 14, "bold"),
            bg=bg_color,
            fg=year_color,
            anchor='w'
        )
        year_label.pack(fill='x')
        
        # Szenarien für dieses Jahr
        scenario_groups = {
            "🇩🇪 Deutschland": [f'de_single_{year}'],
            "📍 4 Zonen": [f'z4_insel_{year}', f'z4_coupled_{year}', f'z4_diff_{year}'],
            "🧭 Nord-Süd": [f'ns_insel_{year}', f'ns_coupled_{year}', f'ns_diff_{year}']
        }
        
        for group_name, group_scenarios in scenario_groups.items():
            # Gruppen-Container
            group_frame = tk.Frame(scrollable_frame, bg=bg_color)
            group_frame.pack(fill='x', pady=(8, 2), padx=20)
            
            group_label = tk.Label(
                group_frame,
                text=group_name,
                font=("Segoe UI", 10),
                bg=bg_color,
                fg="#aaaaaa",
                anchor='w'
            )
            group_label.pack(fill='x')
            
            for scenario_id in group_scenarios:
                if scenario_id in scenario_ids and 'epex' not in scenario_id:
                    cfg = config.SCENARIOS.get(scenario_id, {})
                    # Kurze Beschreibung
                    if 'insel' in scenario_id:
                        desc = 'Inselbetrachtung'
                    elif 'coupled' in scenario_id:
                        desc = 'Gekoppelt'
                    elif 'diff' in scenario_id:
                        desc = 'Preisdifferenz'
                    elif 'single' in scenario_id:
                        desc = 'Eine Zone'
                    else:
                        desc = scenario_id
                    
                    btn = create_button(group_frame, scenario_id, desc, year)
                    btn.pack(pady=2)
    
    # Trennlinie vor Beenden
    separator2 = tk.Frame(scrollable_frame, height=2, bg="#444444")
    separator2.pack(fill='x', pady=20)
    
    # Info-Text
    info_text = tk.Label(
        scrollable_frame,
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
        scrollable_frame,
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
    exit_btn.pack(pady=15)
    
    # Escape zum Schließen
    root.bind('<Escape>', lambda e: root.destroy())
    
    root.mainloop()
    
    return selected[0]


def ask_video_format():
    """
    Fragt den Benutzer nach dem gewünschten Videoformat.
    Gibt zurück: 'mp4', 'gif', 'both' oder None (bei Abbruch).
    """
    result = [None]
    
    # Dialog-Fenster erstellen
    dialog = tk.Toplevel()
    dialog.title("Export Format")
    dialog.geometry("400x250")
    dialog.configure(bg="#2b2b2b")
    dialog.resizable(False, False)
    
    # Zentrieren
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
    y = (dialog.winfo_screenheight() // 2) - (250 // 2)
    dialog.geometry(f"+{x}+{y}")
    
    # Modal machen (Hauptfenster blockieren)
    dialog.transient()
    dialog.grab_set()
    
    tk.Label(
        dialog, 
        text="In welchem Format speichern?", 
        font=("Segoe UI", 12, "bold"),
        bg="#2b2b2b", fg="#ffffff"
    ).pack(pady=20)
    
    def set_res(val):
        result[0] = val
        dialog.destroy()
    
    btn_style = {
        "font": ("Segoe UI", 10),
        "bg": "#3d3d3d", "fg": "#ffffff",
        "activebackground": "#4d4d4d", "activeforeground": "#ffffff",
        "relief": "flat", "width": 30, "cursor": "hand2"
    }
    
    tk.Button(dialog, text="🎥  Nur MP4 (Video)", command=lambda: set_res('mp4'), **btn_style).pack(pady=5)
    tk.Button(dialog, text="🎞️  Nur GIF (Animation)", command=lambda: set_res('gif'), **btn_style).pack(pady=5)
    tk.Button(dialog, text="✨  Beide speichern", command=lambda: set_res('both'), **btn_style).pack(pady=5)
    
    tk.Button(
        dialog, text="Abbrechen", 
        command=lambda: set_res(None),
        font=("Segoe UI", 9), bg="#8b0000", fg="#ffffff", relief="flat", width=15
    ).pack(pady=20)
    
    dialog.wait_window()
    return result[0]

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