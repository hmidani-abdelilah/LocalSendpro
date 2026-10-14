import flet as ft

def main(page: ft.Page):
    # Track the active state of the Control key manually
    ctrl_pressed = False

    def handle_key_down(e: ft.KeyDownEvent):
        nonlocal ctrl_pressed
        
        # Check if Control key is being held down
        if "Control" in e.key:
            ctrl_pressed = True
            
        # Detect the shortcut combination
        if ctrl_pressed and e.key == "A":
            print("Select All pressed locally!")

    def handle_key_up(e: ft.KeyUpEvent):
        nonlocal ctrl_pressed
        if "Control" in e.key:
            ctrl_pressed = False

    keyboard = ft.KeyboardListener(
        autofocus=True,
        on_key_down=handle_key_down,
        on_key_up=handle_key_up,
        content=ft.Container(
            content=ft.Text("Focus here and press Ctrl + A"),
            padding=20,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
        )
    )
    
    page.add(keyboard)

ft.run(main)
