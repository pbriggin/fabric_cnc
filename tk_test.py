import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Tkinter Test App")
    root.geometry("400x200")

    label = ttk.Label(root, text="Hello, Tkinter!", font=("Arial", 18))
    label.pack(pady=20)

    button = ttk.Button(root, text="Click Me", command=lambda: label.config(text="Button Clicked!"))
    button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main() 