import asyncio

import flet as ft


async def main(page: ft.Page):
    auto_scroll_switch = ft.Switch(
        thumb_icon=ft.Icons.LIST_OUTLINED,
        value=False,
        label="Auto-scroll",
        label_position=ft.LabelPosition.RIGHT,
    )

    def handle_switch_change(e: ft.Event[ft.Switch]):
        lv.auto_scroll = not lv.auto_scroll
        lv.update()

    async def handle_mouse_scroll(e: ft.ScrollEvent):
        if not e.scroll_delta.y:
            return
        if lv.auto_scroll:
            lv.auto_scroll = False
            auto_scroll_switch.value = False
            auto_scroll_switch.update()
        await lv.scroll_to(delta=e.scroll_delta.y)

    auto_scroll_switch.on_change = handle_switch_change

    lv = ft.ListView(
        horizontal=True,
        spacing=10,
        padding=20,
        width=600,
        height=400,
        auto_scroll=False,
        scroll=ft.Scrollbar(
            thumb_visibility=False,
            track_visibility=False,
            interactive=True,
            thickness=12,
        ),
        controls=[
            ft.Container(
                content=ft.Text(f"Line {i}", color=ft.Colors.ON_SECONDARY),
                width=120,
                height=360,
                bgcolor=ft.Colors.GREY_700,
                padding=10,
            )
            for i in range(0, 60)
        ],
    )

    page.add(
        ft.SafeArea(
            expand=True,
            content=ft.Row(
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.GREY_500,
                        content=ft.GestureDetector(
                            content=lv,
                            on_scroll=handle_mouse_scroll,
                        ),
                    ),
                    auto_scroll_switch,
                ],
            ),
        )
    )

    # Add a new item to the ListView every second.
    for i in range(len(lv.controls), 120):
        await asyncio.sleep(1)
        lv.controls.append(
            ft.Container(
                content=ft.Text(f"Line {i}", color=ft.Colors.ON_SECONDARY),
                width=120,
                height=360,
                bgcolor=ft.Colors.GREY_700,
                padding=10,
            )
        )
        lv.update()


if __name__ == "__main__":
    ft.run(main)
