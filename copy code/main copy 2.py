import flet as ft

def main(page: ft.Page):
    # إعدادات نافذة التطبيق لتلائم كل المنصات (سطح المكتب والهواتف)
    page.title = "LocalSend Pro - واجهة التطبيق"
    page.vertical_alignment = ft.MainAxisAlignment.END
    page.window.width = 420
    page.window.height = 780
    page.padding = 15
    page.spacing = 10

    # إدارة الثيم (مظهر النظام، الوضع الداكن، الفاتح)
    def apply_theme(theme_choice):
        if theme_choice == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif theme_choice == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        page.update()

    apply_theme("system")

    # --- عناصر الواجهة الأساسية ---
    chat_list = ft.ListView(expand=True, spacing=12, auto_scroll=True)
    devices_list = ft.ListView(horizontal=True, spacing=10, height=55)
    
    # مؤشرات التقدم والسرعة
    progress_bar = ft.ProgressBar(value=0, visible=False, height=8, border_radius=4)
    progress_text = ft.Text("0%", size=11, weight=ft.FontWeight.BOLD, visible=False)
    speed_status_text = ft.Text("🚀 الرفع: 0 B/s | 📥 التحميل: 0 B/s", size=11, color="grey")

    # --- محاكاة أجهزة وهمية في الواجهة ---
    mock_devices = [
        {"name": "حاسوب المكتب (Windows)", "ip": "192.168.1.15", "type": "pc"},
        {"name": "هاتف سامسونج (Android)", "ip": "192.168.1.22", "type": "phone"},
    ]

    def load_mock_devices():
        devices_list.controls.clear()
        for dev in mock_devices:
            devices_list.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PHONE_ANDROID if dev['type'] == "phone" else ft.Icons.LAPTOP, size=18, color="blue"),
                        # تحديد لون نص واضح ومقروء تماماً
                        ft.Text(f"{dev['name']}", size=12, weight=ft.FontWeight.W_500, color="black"),
                    ], spacing=6),
                    padding=10,
                    border_radius=20,
                    bgcolor="white"  # خلفية بيضاء تضمن وضوح النص
                )
            )
        page.update()

    load_mock_devices()

    # --- دالة إضافة فقاعات المحادثة والرسائل ---
    def add_chat_bubble(text, is_me=True, color=None):
        bg_color = "blue900" if is_me else "grey300"
        if color == "orange": bg_color = "orange900"
        elif color == "green": bg_color = "green900"
        elif color == "red": bg_color = "red900"

        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(text, size=13, color="white" if is_me else "black"),
                        padding=12,
                        border_radius=12,
                        bgcolor=bg_color,
                        width=300
                    )
                ],
                alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
            )
        )
        page.update()

    # رسالة ترحيبية تجريبية للواجهة
    add_chat_bubble("مرحباً بك في LocalSend Pro! الواجهة تعمل بكفاءة تامة.", is_me=False, color="green")

    # --- نافذة الإعدادات (Settings Dialog) ---
    def open_settings(e):
        # تم إزالة border_radius المباشر من الحقول لتجنب التحذيرات
        name_input = ft.TextField(label="اسم الجهاز في الشبكة", value="My_Device")
        port_input = ft.TextField(label="منفذ الاتصال (Port)", value="50006")
        theme_dropdown = ft.Dropdown(
            label="مظهر التطبيق",
            value="system",
            options=[
                ft.dropdown.Option("system", "اتباع مظهر النظام"),
                ft.dropdown.Option("dark", "الوضع الداكن"),
                ft.dropdown.Option("light", "الوضع الفاتح")
            ]
        )

        def save_settings(dlg_e):
            apply_theme(theme_dropdown.value)
            settings_dialog.open = False
            add_chat_bubble(f"⚙ تم تحديث الإعدادات بنجاح (الاسم: {name_input.value})", is_me=True)
            page.update()

        settings_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.SETTINGS), ft.Text("إعدادات التطبيق")]),
            content=ft.Column([name_input, port_input, theme_dropdown], height=210, tight=True),
            actions=[
                ft.Button(content=ft.Text("حفظ"), on_click=save_settings),
                ft.Button(content=ft.Text("إلغاء"), on_click=lambda _: setattr(settings_dialog, 'open', False) or page.update())
            ],
            shape=ft.RoundedRectangleBorder(radius=15)
        )
        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS_ROUNDED,
        icon_size=22,
        tooltip="الإعدادات",
        on_click=open_settings
    )

    # --- نافذة اختيار الجهاز عند إرسال ملف ---
    def open_device_selector(file_name):
        options = [ft.dropdown.Option(key=dev['ip'], text=f"{dev['name']} ({dev['ip']})") for dev in mock_devices]
        device_dropdown = ft.Dropdown(label="اختر الجهاز الهدف للإرسال", options=options, value=options[0].key)

        def confirm_send(dlg_e):
            selector_dialog.open = False
            page.update()
            add_chat_bubble(f"🚀 جاري إرسال الملف [{file_name}]...", is_me=True)
            progress_bar.visible = True
            progress_text.visible = True
            progress_bar.value = 0.5
            progress_text.value = "الإرسال: 50%"
            page.update()

        selector_dialog = ft.AlertDialog(
            title=ft.Text("اختر جهاز الاستقبال"),
            content=ft.Column([device_dropdown], height=100, tight=True),
            actions=[
                ft.Button(content=ft.Text("إرسال"), on_click=confirm_send),
                ft.Button(content=ft.Text("إلغاء"), on_click=lambda _: setattr(selector_dialog, 'open', False) or page.update())
            ]
        )
        page.overlay.append(selector_dialog)
        selector_dialog.open = True
        page.update()

    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files:
            file_name = e.files[0].name
            open_device_selector(file_name)

    file_picker = ft.FilePicker(on_result=on_file_result)
    page.services.append(file_picker)

    # --- حل مشكلة الكوروتين عبر دالة غير متزامنة (async) ---
    async def pick_file_async(e):
        await file_picker.pick_files(allow_multiple=False)

    def send_message(e):
        if message_input.value:
            add_chat_bubble(message_input.value, is_me=True)
            message_input.value = ""
            page.update()

    message_input = ft.TextField(
        hint_text="اكتب رسالتك هنا...",
        expand=True,
        border_radius=25,
        on_submit=send_message,
        text_size=13
    )

    send_button = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_color="white",
        bgcolor="blue",
        on_click=send_message,
        tooltip="إرسال رسالة"
    )

    file_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        icon_color="blue",
        tooltip="إرسال ملف",
        on_click=pick_file_async  # استخدام الدالة الـ async المنتظرة
    )

    page.add(
        ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.WIFI_TETHERING, color="green", size=22),
                ft.Text("LocalSend Pro (UI)", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            settings_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        
        ft.Text("الأجهزة المتاحة في الشبكة:", size=12, weight=ft.FontWeight.BOLD, color="grey"),
        devices_list,
        ft.Divider(height=1, color="grey400"),
        
        chat_list,
        
        ft.Column([
            speed_status_text,
            progress_text,
            progress_bar
        ], spacing=3),
        
        ft.Row([file_button, message_input, send_button], spacing=5)
    )

if __name__ == "__main__":
    ft.run(main)