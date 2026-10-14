import socket
import threading
import os
import flet as ft
from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser

SERVICE_TYPE = "_localsend._tcp.local."
HOSTNAME = socket.gethostname()

app_config = {
    "device_name": f"Device_{HOSTNAME}",
    "tcp_port": 50006,
    "theme": "system"
}

discovered_devices = {}
active_zeroconf = None
active_service_info = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = '127.0.0.1'
    finally:
        s.close()
    return ip_address

def main(page: ft.Page):
    page.title = "LocalSend - مشاركة الملفات"
    page.vertical_alignment = ft.MainAxisAlignment.END
    page.window.width = 420
    page.window.height = 750
    page.padding = 15
    page.spacing = 10

    def apply_theme(theme_choice):
        if theme_choice == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif theme_choice == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        page.update()

    apply_theme(app_config["theme"])

    # قائمة عرض الرسائل بتصميم أنيق
    chat_list = ft.ListView(expand=True, spacing=12, auto_scroll=True)
    
    # قائمة الأجهزة المتصلة
    devices_list = ft.ListView(horizontal=True, spacing=10, height=55)
    
    # شريط التقدم بتصميم عصري
    progress_bar = ft.ProgressBar(value=0, visible=False, height=8, border_radius=4)
    progress_text = ft.Text("0%", size=11, weight=ft.FontWeight.BOLD)

    global active_zeroconf, active_service_info

    class FletLocalSendListener:
        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if info:
                addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
                ip = addresses[0] if addresses else None
                dev_name = info.properties.get(b'device_name', b'Unknown').decode('utf-8')
                if ip and ip != get_local_ip():
                    discovered_devices[name] = {'name': dev_name, 'ip': ip, 'port': info.port}
                    update_devices_ui()

        def remove_service(self, zc, type_, name):
            if name in discovered_devices:
                del discovered_devices[name]
                update_devices_ui()

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

    def update_devices_ui():
        devices_list.controls.clear()
        if not discovered_devices:
            devices_list.controls.append(
                ft.Row([
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text("جاري البحث عن أجهزة قريبة...", italic=True, size=12, color=ft.Colors.GREY)
                ], spacing=10)
            )
        else:
            for dev in discovered_devices.values():
                devices_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PHONE_ANDROID if "Android" in dev['name'] else ft.Icons.LAPTOP, size=18, color=ft.Colors.BLUE_400),
                            ft.Text(f"{dev['name']}", size=12, weight=ft.FontWeight.W_500),
                        ], spacing=6),
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border_radius=20,
                        bgcolor=ft.Colors.SURFACE_VARIANT,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT)
                    )
                )
        page.update()

    def init_network():
        global active_zeroconf, active_service_info
        try:
            if active_zeroconf:
                active_zeroconf.unregister_service(active_service_info)
                active_zeroconf.close()

            active_zeroconf = Zeroconf()
            local_ip = get_local_ip()
            active_service_info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=f"{HOSTNAME}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=app_config["tcp_port"],
                properties={'device_name': app_config["device_name"]},
                server=f"{HOSTNAME}.local."
            )
            active_zeroconf.register_service(active_service_info)
            ServiceBrowser(active_zeroconf, SERVICE_TYPE, FletLocalSendListener())
        except Exception as e:
            print(f"Network Error: {e}")

    threading.Thread(target=init_network, daemon=True).start()

    # دالة إضافة رسالة بتصميم فقاعة (Bubble)
    def add_chat_bubble(text, is_me=True, color=None):
        bg_color = ft.Colors.BLUE_900 if is_me else ft.Colors.SURFACE_VARIANT
        if color == "orange":
            bg_color = ft.Colors.ORANGE_900
        elif color == "green":
            bg_color = ft.Colors.GREEN_900
        elif color == "red":
            bg_color = ft.Colors.RED_900

        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(text, size=13, color=ft.Colors.WHITE),
                        padding=12,
                        border_radius=12,
                        bgcolor=bg_color,
                        constraints=ft.BoxConstraints(maxWidth=300)
                    )
                ],
                alignment=ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
            )
        )
        page.update()

    # خادم الاستلام
    def tcp_file_receiver():
        while True:
            try:
                server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.bind(('', app_config["tcp_port"]))
                server_sock.listen(5)
                
                while True:
                    client, addr = server_sock.accept()
                    try:
                        header = client.recv(1024).decode('utf-8')
                        if header.startswith("FILE:"):
                            _, filename, filesize = header.split(":")
                            filesize = int(filesize)
                            
                            add_chat_bubble(f"📥 طلب استلام ملف من {addr[0]}: {filename}", is_me=False, color="orange")
                            client.sendall("ACCEPT".encode('utf-8'))

                            progress_bar.visible = True
                            progress_text.visible = True
                            progress_bar.value = 0
                            page.update()

                            save_path = f"received_{os.path.basename(filename)}"
                            received_bytes = 0

                            with open(save_path, 'wb') as f:
                                while received_bytes < filesize:
                                    chunk = client.recv(4096)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    received_bytes += len(chunk)
                                    
                                    progress_bar.value = received_bytes / filesize
                                    progress_text.value = f"جاري الاستلام... {int(progress_bar.value * 100)}%"
                                    page.update()

                            add_chat_bubble(f"✔ تم استلام وحفظ الملف بنجاح: {save_path}", is_me=False, color="green")
                            progress_bar.visible = False
                            progress_text.visible = False
                            page.update()
                    except Exception as e:
                        print(f"Receiver Inner Error: {e}")
                    finally:
                        client.close()
            except Exception as e:
                import time
                time.sleep(3)

    threading.Thread(target=tcp_file_receiver, daemon=True).start()

    # نافذة الإعدادات
    def open_settings(e):
        name_input = ft.TextField(label="اسم الجهاز في الشبكة", value=app_config["device_name"], border_radius=10)
        port_input = ft.TextField(label="منفذ الاتصال (Port)", value=str(app_config["tcp_port"]), border_radius=10)
        
        theme_dropdown = ft.Dropdown(
            label="مظهر التطبيق",
            value=app_config["theme"],
            border_radius=10,
            options=[
                ft.dropdown.Option("system", "اتباع مظهر النظام"),
                ft.dropdown.Option("dark", "الوضع الداكن"),
                ft.dropdown.Option("light", "الوضع الفاتح")
            ]
        )

        def save_settings(dlg_e):
            try:
                new_port = int(port_input.value)
            except ValueError:
                add_chat_bubble("❌ خطأ: رقم البورت غير صالح!", is_me=False, color="red")
                return

            app_config["device_name"] = name_input.value
            app_config["tcp_port"] = new_port
            app_config["theme"] = theme_dropdown.value
            
            apply_theme(app_config["theme"])
            threading.Thread(target=init_network, daemon=True).start()
            
            settings_dialog.open = False
            add_chat_bubble(f"⚙ تم حفظ الإعدادات بنجاح", is_me=True)
            page.update()

        settings_dialog = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.SETTINGS), ft.Text("إعدادات التطبيق")]),
            content=ft.Column([name_input, port_input, theme_dropdown], height=210, tight=True),
            actions=[
                ft.ElevatedButton("حفظ", on_click=save_settings),
                ft.TextButton("إلغاء", on_click=lambda _: setattr(settings_dialog, 'open', False) or page.update())
            ],
            shape=ft.RoundedRectangleBorder(radius=15)
        )
        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    # زر الإعدادات الأنيق
    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS_ROUNDED,
        icon_size=22,
        tooltip="الإعدادات",
        on_click=open_settings
    )

    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files:
            file_path = e.files[0].path
            filename = e.files[0].name
            filesize = e.files[0].size

            if not discovered_devices:
                add_chat_bubble("⚠ لا توجد أجهزة متصلة في الشبكة حالياً!", is_me=False, color="red")
                return

            target = list(discovered_devices.values())[0]

            def send_task():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((target['ip'], target['port']))
                    sock.sendall(f"FILE:{filename}:{filesize}".encode('utf-8'))

                    response = sock.recv(1024).decode('utf-8')
                    if response == "ACCEPT":
                        progress_bar.visible = True
                        progress_text.visible = True
                        progress_bar.value = 0
                        page.update()

                        sent_bytes = 0
                        with open(file_path, 'rb') as f:
                            while True:
                                chunk = f.read(4096)
                                if not chunk:
                                    break
                                sock.sendall(chunk)
                                sent_bytes += len(chunk)
                                
                                progress_bar.value = sent_bytes / filesize
                                progress_text.value = f"جاري الإرسال... {int(progress_bar.value * 100)}%"
                                page.update()

                        add_chat_bubble(f"🚀 تم إرسال الملف [{filename}] بنجاح إلى {target['name']}", is_me=True)
                    else:
                        add_chat_bubble("❌ رفض الطرف الآخر استقبال الملف.", is_me=False, color="red")
                except Exception as ex:
                    add_chat_bubble(f"❌ خطأ في الإرسال: {ex}", is_me=False, color="red")
                finally:
                    progress_bar.visible = False
                    progress_text.visible = False
                    sock.close()
                    page.update()

            threading.Thread(target=send_task, daemon=True).start()

    file_picker = ft.FilePicker(on_result=on_file_result)
    page.services.append(file_picker)

    def send_message(e):
        if message_input.value:
            add_chat_bubble(message_input.value, is_me=True)
            message_input.value = ""
            page.update()

    # إدخال النصوص والأزرار بتصميم عصري (Buttons with Icons)
    message_input = ft.TextField(
        hint_text="اكتب رسالتك هنا...",
        expand=True,
        border_radius=25,
        content_padding=ft.padding.symmetric(horizontal=20, vertical=10),
        on_submit=send_message,
        text_size=13
    )

    send_button = ft.IconButton(
        icon=ft.Icons.SEND_ROUNDED,
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE,
        on_click=send_message,
        tooltip="إرسال رسالة"
    )

    file_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        icon_color=ft.Colors.BLUE_400,
        tooltip="إرسال ملف",
        on_click=lambda _: file_picker.pick_files(allow_multiple=False)
    )

    # التخطيط الرئيسي للشاشة
    page.add(
        # الهيدر العلوي
        ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.WIFI_TETHERING, color=ft.Colors.GREEN_400, size=22),
                ft.Text("LocalSend LAN", weight=ft.FontWeight.BOLD, size=16),
            ], spacing=8),
            settings_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        
        # قسم الأجهزة المكتشفة
        ft.Text("الأجهزة المتاحة:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY),
        devices_list,
        ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
        
        # قائمة المحادثة
        chat_list,
        
        # شريط التقدم والنسبة
        ft.Column([
            progress_text,
            progress_bar
        ], spacing=2),
        
        # شريط الإدخال السفلي
        ft.Row([file_button, message_input, send_button], spacing=5)
    )

if __name__ == "__main__":
    ft.run(main)