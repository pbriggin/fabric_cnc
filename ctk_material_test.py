import customtkinter as ctk

# Material Design-inspired color palette
PRIMARY_COLOR = '#6200ee'  # Material Deep Purple 500
ON_PRIMARY = '#ffffff'
BACKGROUND = '#f5f5f5'
SURFACE = '#ffffff'
ON_SURFACE = '#222222'

ctk.set_appearance_mode("light")  # or "system" for auto
ctk.set_default_color_theme("blue")  # closest to Material by default

def main():
    root = ctk.CTk()
    root.title("Material Design CustomTkinter App")
    root.geometry("420x260")
    root.configure(bg=BACKGROUND)

    # App Bar (Top)
    app_bar = ctk.CTkFrame(root, fg_color=PRIMARY_COLOR, corner_radius=0, height=56)
    app_bar.pack(fill="x", side="top")
    title = ctk.CTkLabel(app_bar, text="Fabric CNC", text_color=ON_PRIMARY, font=("Roboto", 20, "bold"))
    title.pack(side="left", padx=24, pady=12)

    # Main Content
    content = ctk.CTkFrame(root, fg_color=SURFACE, corner_radius=12)
    content.pack(expand=True, fill="both", padx=24, pady=(24, 16))

    label = ctk.CTkLabel(content, text="Welcome to Material Design!", text_color=ON_SURFACE, font=("Roboto", 16))
    label.pack(pady=(32, 16))

    def on_click():
        label.configure(text="Button Clicked!", text_color=PRIMARY_COLOR)

    button = ctk.CTkButton(content, text="Primary Action", fg_color=PRIMARY_COLOR, text_color=ON_PRIMARY, hover_color="#3700b3", command=on_click, font=("Roboto", 14, "bold"), corner_radius=8)
    button.pack(pady=8)

    root.mainloop()

if __name__ == "__main__":
    main() 