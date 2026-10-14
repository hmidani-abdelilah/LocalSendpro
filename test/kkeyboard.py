import flet as ft

def main(page: ft.Page):
    def on_keyboard(e: ft.KeyboardEvent):
        print(f"Key: {e.key}, Shift: {e.shift}, Ctrl: {e.ctrl}, Alt: {e.alt}, Meta: {e.meta}")
        
        # Example shortcut: Ctrl + S
        if e.ctrl and e.key == "S":
            print("Saved!")

    page.on_keyboard_event = on_keyboard

ft.run(main)
