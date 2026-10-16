"""Local network file sharing with a Flet interface."""

import asyncio
import base64
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import flet as ft
import flet_audio as fta
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes

from crypto_utils import (
    decrypt_file_chunk,
    decrypt_message_payload,
    encrypt_file_chunk,
    encrypt_message,
)

try:
    import psutil
except ImportError:
    psutil = None


SERVICE_TYPE = "_localsend._tcp.local."
HOSTNAME = socket.gethostname()
DEFAULT_PORT = 50006
CHUNK_SIZE = 64 * 1024


def local_file_path(value):
    """Convert a picker path or Android java.io.File proxy to a real path."""
    if value is None:
        return None
    if isinstance(value, os.PathLike):
        return Path(value)
    if isinstance(value, str):
        return Path(value)
    for method_name in ("getAbsolutePath", "getPath"):
        method = getattr(value, method_name, None)
        if callable(method):
            path = method()
            if path:
                return Path(str(path))
    return None


def ensure_writable_directory(path: Path) -> Path:
    """Create a directory and verify that this process can write to it."""
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".localsend_write_test_{os.urandom(4).hex()}.tmp"
    probe.write_bytes(b"")
    probe.unlink(missing_ok=True)
    return path


def get_settings_db_path() -> Path:
    """Return a writable per-user database path, including Android app storage."""
    try:
        context, _ = get_android_context()
        app_files = context.getFilesDir()
        if app_files is not None:
            app_files_path = local_file_path(app_files)
            if app_files_path is not None:
                return app_files_path / "localsend_settings.sqlite3"
    except Exception:
        pass
    return Path.home() / ".localsendpro" / "settings.sqlite3"


def load_app_settings(defaults: dict) -> dict:
    """Create the settings table on first launch and return saved values."""
    database_path = get_settings_db_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                device_name TEXT NOT NULL,
                port INTEGER NOT NULL,
                theme TEXT NOT NULL,
                receive_dir_mode TEXT NOT NULL,
                receive_dir TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT OR IGNORE INTO app_settings
               (id, device_name, port, theme, receive_dir_mode, receive_dir)
               VALUES (1, ?, ?, ?, ?, ?)""",
            (
                defaults["device_name"], defaults["port"], defaults["theme"],
                defaults["receive_dir_mode"], defaults["receive_dir"],
            ),
        )
        row = connection.execute(
            """SELECT device_name, port, theme, receive_dir_mode, receive_dir
               FROM app_settings WHERE id = 1"""
        ).fetchone()
    values = dict(zip(
        ("device_name", "port", "theme", "receive_dir_mode", "receive_dir"), row
    ))
    if not 1 <= int(values["port"]) <= 65535:
        values["port"] = defaults["port"]
    if values["theme"] not in ("system", "dark", "light"):
        values["theme"] = defaults["theme"]
    if values["receive_dir_mode"] not in ("downloads", "custom"):
        values["receive_dir_mode"] = defaults["receive_dir_mode"]
    if str(values["receive_dir"]).startswith("<java.io.File at "):
        values["receive_dir"] = defaults["receive_dir"]
        values["receive_dir_mode"] = "downloads"
    return values


def save_app_settings(settings: dict) -> None:
    """Persist the current device and interface settings in SQLite."""
    database_path = get_settings_db_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                device_name TEXT NOT NULL,
                port INTEGER NOT NULL,
                theme TEXT NOT NULL,
                receive_dir_mode TEXT NOT NULL,
                receive_dir TEXT NOT NULL
            )"""
        )
        connection.execute(
            """INSERT INTO app_settings
               (id, device_name, port, theme, receive_dir_mode, receive_dir)
               VALUES (1, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   device_name=excluded.device_name,
                   port=excluded.port,
                   theme=excluded.theme,
                   receive_dir_mode=excluded.receive_dir_mode,
                   receive_dir=excluded.receive_dir""",
            (
                settings["device_name"], settings["port"], settings["theme"],
                settings["receive_dir_mode"], settings["receive_dir"],
            ),
        )


def get_android_activity():
    """Return the native Android Activity exposed by Flet, if available."""
    from jnius import autoclass

    activity_host_class = os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME")
    # The holder class package differs between Serious Python releases. Prefer
    # Flet's advertised class, then try the package names used by its runtimes.
    host_classes = list(dict.fromkeys(
        name
        for name in (
            activity_host_class,
            "com.flet.serious_python.PythonActivity",
            "com.flet.serious_python_android.PythonActivity",
        )
        if name
    ))
    last_error = None
    for host_class in host_classes:
        try:
            activity = autoclass(host_class).mActivity
            if activity is not None:
                return activity, autoclass
        except Exception as error:
            last_error = error
    if not host_classes:
        raise RuntimeError("Flet لم يوفّر مضيف النشاط الأصلي")
    raise RuntimeError(f"تعذر الوصول إلى نشاط Android عبر Flet: {last_error}")


def get_android_context():
    """Return the Android application context, independent of Flet's holder class."""
    from jnius import autoclass

    try:
        activity, _ = get_android_activity()
        context = activity.getApplicationContext()
        if context is not None:
            return context, autoclass
    except Exception:
        pass

    # Wake locks only need an application Context. This avoids relying on the
    # holder class name, which differs between Serious Python releases.
    try:
        context = autoclass("android.app.ActivityThread").currentApplication()
        if context is not None:
            return context, autoclass
    except Exception:
        pass

    raise RuntimeError("تعذر الحصول على سياق تطبيق Android")


def get_local_ip():
    """Return the IPv4 address used by the active local network interface."""
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connection.connect(("10.255.255.255", 1))
        return connection.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        connection.close()


def format_speed(bytes_per_second):
    """Format a byte-per-second value using a readable unit."""
    if bytes_per_second >= 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.2f} MB/s"
    if bytes_per_second >= 1024:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    return f"{bytes_per_second:.0f} B/s"


def get_received_files_dir() -> Path:
    """Return the system Downloads directory for the current platform."""
    try:
        context, autoclass = get_android_context()
        env = autoclass("android.os.Environment")
    except Exception:
        pass
    else:
        try:
            public_downloads = env.getExternalStoragePublicDirectory(
                env.DIRECTORY_DOWNLOADS
            )
            download_dir = local_file_path(public_downloads)
            if download_dir is not None:
                return ensure_writable_directory(download_dir)
        except Exception:
            pass
        try:
            external_dir = context.getExternalFilesDir(env.DIRECTORY_DOWNLOADS)
            download_dir = local_file_path(external_dir)
            if download_dir is not None:
                return ensure_writable_directory(download_dir)
        except Exception:
            pass

    for base in (
        Path.home() / "Downloads",
        Path("/storage/emulated/0/Download"),
        Path("/sdcard/Download"),
        Path("/mnt/sdcard/Download"),
        Path("/storage/emulated/0"),
        Path("/sdcard"),
        Path("/mnt/sdcard"),
    ):
        try:
            return ensure_writable_directory(base)
        except OSError:
            continue

    return Path.home() / "Downloads"


def safe_receive_dir(path: str | Path | None) -> Path:
    """Validate a chosen directory and return the system Downloads fallback if not writable."""
    if isinstance(path, str) and path.startswith("<java.io.File at "):
        candidate = get_received_files_dir()
    else:
        candidate = normalize_receive_dir(path)
    try:
        return ensure_writable_directory(candidate)
    except (OSError, PermissionError):
        return get_received_files_dir()


def choose_folder_path(initial_dir: str | Path | None = None) -> str | None:
    """Open a native folder chooser on desktop systems and return the chosen path."""
    initial_dir = str(initial_dir or get_received_files_dir())
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askdirectory(
            initialdir=initial_dir,
            title="اختر مجلد حفظ الملفات",
        )
        root.destroy()
        return selected or None
    except Exception:
        return None


def normalize_receive_dir(raw_path: str | Path | None) -> Path:
    """Resolve a custom receive-directory path into an absolute path."""
    if not raw_path or not str(raw_path).strip():
        return get_received_files_dir()
    if isinstance(raw_path, str) and raw_path.startswith("<java.io.File at "):
        return get_received_files_dir()
    candidate = local_file_path(raw_path)
    if candidate is None:
        return get_received_files_dir()
    candidate = candidate.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate


def get_receive_dir(config=None) -> Path:
    """Return the current target directory for incoming files."""
    config = config or {}
    mode = config.get("receive_dir_mode", "downloads")
    if mode == "downloads":
        return get_received_files_dir()
    explicit_path = config.get("receive_dir")
    if explicit_path:
        return safe_receive_dir(explicit_path)
    return safe_receive_dir(Path.cwd() / "received_files")


def open_receive_directory(page: ft.Page, config=None):
    """Open the configured save directory in the system file manager when possible."""
    target_dir = get_receive_dir(config)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if page.platform is not None and page.platform.is_mobile():
            mActivity, autoclass = get_android_activity()

            intent = autoclass("android.content.Intent")()
            intent.setAction(autoclass("android.content.Intent").ACTION_VIEW)

            android_uri = None
            try:
                android_uri = autoclass("android.net.Uri").parse(
                    "content://downloads/all_downloads"
                )
            except Exception:
                android_uri = None

            if android_uri is not None:
                try:
                    intent.setDataAndType(android_uri, "vnd.android.document/directory")
                    mActivity.startActivity(intent)
                    return
                except Exception:
                    pass

            try:
                uri = autoclass("android.net.Uri").fromFile(str(target_dir))
                intent.setDataAndType(uri, "*/*")
                mActivity.startActivity(intent)
                return
            except Exception:
                pass

            try:
                downloads_dir = get_received_files_dir()
                uri = autoclass("android.net.Uri").fromFile(str(downloads_dir))
                intent.setDataAndType(uri, "vnd.android.document/directory")
                mActivity.startActivity(intent)
                return
            except Exception:
                pass
    except Exception:
        pass

    try:
        if os.name == "nt":
            os.startfile(str(target_dir))
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target_dir)])
            return
        subprocess.Popen(["xdg-open", str(target_dir)])
        return
    except Exception:
        pass

    try:
        page.launch_url(f"file:///{target_dir.as_posix()}")
    except Exception:
        pass


def main(page: ft.Page):
    """Build the interface and start discovery, transfer, and speed services."""
    page.title = "LocalSend Pro"
    page.vertical_alignment = ft.MainAxisAlignment.END
    page.window.top = 100
    page.window.left = 100
    page.window.width = 440
    page.window.height = 780
    page.padding = 15
    page.spacing = 10


    # 1. عرض شاشة البداية "المزيفة"
    splash_image = ft.Image(
        src="splash_web.png",  # ضع صورة شاشة البداية في مجلد assets
        width=300,
        height=300,
        fit=ft.BoxFit.CONTAIN)
    
    page.add(ft.Column([splash_image], alignment=ft.MainAxisAlignment.CENTER, expand=True))
    page.update()
    
    # محاكاة وقت التحميل (استبدله بالتحميل الحقيقي لبياناتك)
    time.sleep(2)
    
    # 2. مسح الشاشة وعرض واجهة التطبيق الرئيسية
    page.clean()


    app_config = {
        "device_name": f"Device_{HOSTNAME}",
        "port": DEFAULT_PORT,
        "theme": "system",
        "receive_dir_mode": "downloads",
        "receive_dir": str(get_received_files_dir()),
    }
    try:
        app_config.update(load_app_settings(app_config))
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Could not load saved settings: {error}")
    device_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    discovered_devices = {}
    devices_lock = threading.RLock()
    receiver_lock = asyncio.Lock()
    session = {"active": True}
    network = {"zeroconf": None, "service": None, "browser": None, "server": None}
    android_network_locks = []

    async def handle_mouse_scroll(e: ft.ScrollEvent):
        delta = e.scroll_delta.y or e.scroll_delta.x
        if not delta:
            return
        await devices_list.scroll_to(delta=delta)

    chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    devices_list = ft.ListView(
        horizontal=True,
        spacing=10,
        height=56,
        auto_scroll=False,
        build_controls_on_demand=False,
        scroll=ft.Scrollbar(
            thumb_visibility=False,
            track_visibility=False,
            interactive=True,
            thickness=8,
        ),
    )
    message_device_dropdown = ft.Dropdown(
        label="المستلم", width=150, options=[], disabled=True,rtl=True
    )
    message_input = ft.TextField(
        hint_text="اكتب رسالة...", expand=True, min_lines=1, max_lines=3,rtl=True
    )
    progress_bar = ft.ProgressBar(value=0, visible=False, height=8, border_radius=4)
    progress_text = ft.Text("", size=11, weight=ft.FontWeight.BOLD, visible=False)
    speed_status_text = ft.Text(
        "رفع: 0 B/s | تحميل: 0 B/s", size=11, color=ft.Colors.GREY,rtl=True
    )
    network_status_text = ft.Text("جارٍ بدء خدمات الشبكة...", size=11,rtl=True)

    def apply_theme(theme_choice):
        """Apply the selected theme to the current page."""
        app_config["theme"] = theme_choice
        page.theme_mode = {
            "dark": ft.ThemeMode.DARK,
            "light": ft.ThemeMode.LIGHT,
        }.get(theme_choice, ft.ThemeMode.SYSTEM)
        page.update()

    def add_activity(text, is_me=False, color=None):
        """Append a transfer or network event to the activity feed."""
        colors = {
            "orange": ft.Colors.ORANGE_900,
            "green": ft.Colors.GREEN_900,
            "red": ft.Colors.RED_900,
        }
        background = colors.get(
            color, ft.Colors.BLUE_900 if is_me else ft.Colors.SURFACE_CONTAINER_HIGHEST
        )
        chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(
                            text,
                            size=13,
                            color=ft.Colors.WHITE if is_me or color else ft.Colors.ON_SURFACE,
                            selectable=True,rtl=True
                        ),
                        padding=12,
                        border_radius=10,
                        bgcolor=background,
                        width=320,
                    )
                ],
                alignment=(
                    ft.MainAxisAlignment.END if is_me else ft.MainAxisAlignment.START
                ),
            )
        )
        page.update()

    notification_audio = None
    notification_file = Path(__file__).resolve().with_name("notification.wav")
    use_system_audio = page.platform == ft.PagePlatform.LINUX and not page.web
    if not use_system_audio:
        notification_audio = fta.Audio(
            src="notification.wav",
            volume=0.75,
            release_mode=fta.ReleaseMode.STOP,
        )
        page.services.append(notification_audio)

    async def play_notification():
        """Play the bundled sound when a transfer needs the user's attention."""
        if use_system_audio and notification_file.is_file():
            try:
                player = await asyncio.create_subprocess_exec(
                    "gst-play-1.0",
                    "--no-interactive",
                    str(notification_file),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await player.wait()
            except Exception as error:
                print(f"Audio notification failed: {error}")
            return

        if notification_audio is not None:
            try:
                await notification_audio.play()
            except Exception as error:
                print(f"Audio notification failed: {error}")
                
    async def on_keyboard_event(e: ft.KeyboardEvent):
        """Handle keyboard shortcuts for sending messages and opening settings."""
        if e.key == "Enter" or e.key == "Numpad Enter" and not e.shift:
            await send_text_message(None)
            e.prevent_default = True
        elif e.key == "S" and e.ctrl:
            await open_settings(None)
            e.prevent_default = True
            
    page.on_keyboard_event = on_keyboard_event
    
    async def select_message_device(device_id):
        """Select a discovered device from its card and prepare the message input."""
        with devices_lock:
            if device_id not in discovered_devices:
                return

        message_device_dropdown.value = device_id
        await refresh_devices()
        await message_input.focus()

    async def refresh_devices():
        """Rebuild the device strip from the latest mDNS discovery results."""
        with devices_lock:
            devices = list(discovered_devices.values())

        previous_target = message_device_dropdown.value
        message_device_dropdown.options = [
            ft.dropdown.Option(
                key=device["id"], text=f"{device['name']} ({device['ip']})"
            )
            for device in devices
        ]
        device_ids = {device["id"] for device in devices}
        message_device_dropdown.value = (
            previous_target if previous_target in device_ids
            else devices[0]["id"] if devices else None
        )
        message_device_dropdown.disabled = not devices

        devices_list.controls.clear()
        if not devices:
            devices_list.controls.append(
                ft.Row(
                    [
                        ft.ProgressRing(width=16, height=16, stroke_width=2),
                        ft.Text("جارٍ البحث عن أجهزة على الشبكة...", size=12,rtl=True),
                    ],
                    spacing=8,
                    auto_scroll=True,
                
                )
                
            )
        else:
            for device in devices:
                devices_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.PHONE_ANDROID
                                    if "android" in device["name"].lower()
                                    else ft.Icons.LAPTOP,
                                    size=18,
                                    color=ft.Colors.BLUE,
                                ),
                                ft.Text(device["name"], size=12, max_lines=1),
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED,
                                    size=16,
                                    color=ft.Colors.BLUE,
                                    visible=device["id"] == message_device_dropdown.value,
                                ),
                            ],
                            spacing=6,
                            auto_scroll=True,
                        ),
                        padding=10,
                        border_radius=8,
                        bgcolor=(
                            ft.Colors.PRIMARY_CONTAINER
                            if device["id"] == message_device_dropdown.value
                            else ft.Colors.SURFACE_CONTAINER_HIGHEST
                        ),
                        on_click=lambda _, device_id=device["id"]: page.run_task(
                            select_message_device, device_id
                        ),
                        tooltip=f"{device['name']} ({device['ip']}:{device['port']})",
                        
                    )
                    
                )
        page.update()
        page.update()
    message_device_dropdown.on_change = lambda _: page.run_task(refresh_devices)

    def schedule_device_refresh():
        """Schedule a UI refresh safely from a Zeroconf callback thread."""
        page.loop.call_soon_threadsafe(page.run_task, refresh_devices)

    async def handle_incoming_file(reader, writer):
        """Route text messages and receive approved files from network peers."""
        source_ip = writer.get_extra_info("peername")[0]
        try:
            prefix = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            if prefix == b"KEY?":
                public_bytes = device_private_key.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                writer.write(len(public_bytes).to_bytes(4, "big") + public_bytes)
                await writer.drain()
                return
            if prefix in (b"MSGE", b"MSGC"):
                size_text = await asyncio.wait_for(reader.readuntil(b"\n"), timeout=10)
                size_fields = size_text[:-1].decode("ascii").split(":")
                if len(size_fields) != 3 or size_fields[0] != "":
                    raise ValueError("Invalid encrypted message header")
                message_size_text, key_size_text = size_fields[1:]
                message_size = int(message_size_text)
                key_size = int(key_size_text)
                if message_size < 0 or key_size != 256:
                    raise ValueError("Invalid encrypted message size")
                wrapped_key = await reader.readexactly(key_size)
                if prefix == b"MSGE":
                    # Backward compatibility with the previous single-chunk protocol.
                    nonce = await reader.readexactly(12)
                    ciphertext = await reader.readexactly(message_size + 16)
                    message_bytes = decrypt_message_payload(
                        device_private_key, wrapped_key, nonce, ciphertext
                    )
                else:
                    wrapped_text = device_private_key.decrypt(
                        wrapped_key,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None,
                        ),
                    )
                    aes_key = base64.urlsafe_b64decode(wrapped_text)
                    nonce_prefix = await reader.readexactly(4)
                    message_buffer = bytearray()
                    received_bytes = 0
                    chunk_index = 0
                    while received_bytes < message_size:
                        plain_size = min(CHUNK_SIZE, message_size - received_bytes)
                        encrypted_chunk = await reader.readexactly(plain_size + 16)
                        message_buffer.extend(
                            decrypt_file_chunk(
                                aes_key, nonce_prefix, chunk_index, encrypted_chunk
                            )
                        )
                        received_bytes += plain_size
                        chunk_index += 1
                    message_bytes = bytes(message_buffer)
                message = message_bytes.decode("utf-8")
                add_activity(f"{source_ip}: {message}")
                writer.write(b"OK")
                await writer.drain()
                return
            if prefix != b"FILE":
                return
            header = prefix + await asyncio.wait_for(reader.readuntil(b"\n"), timeout=10)

            async with receiver_lock:
                filename = ""
                handshake_replied = False
                try:
                    header_text = header.decode("utf-8")
                    encoded_filename = header_text.startswith("FILEE64:")
                    encrypted_transfer = encoded_filename or header_text.startswith("FILEE:")
                    if not encrypted_transfer:
                        raise ValueError("Unencrypted transfers are not accepted")
                    file_details = header_text.split(":", 1)[1].rstrip("\n")
                    filename_field, filesize_text, key_size_text = file_details.rsplit(":", 2)
                    if encoded_filename:
                        filename = base64.urlsafe_b64decode(
                            filename_field.encode("ascii")
                        ).decode("utf-8")
                    else:
                        filename = filename_field
                    key_size = int(key_size_text)
                    if key_size != 256:
                        raise ValueError("Invalid wrapped key size")
                    filename = Path(filename).name
                    filesize = int(filesize_text)
                    if not filename or filesize < 0:
                        raise ValueError("Invalid file name or size")

                    decision = asyncio.get_running_loop().create_future()

                    def answer(accepted):
                        if not decision.done():
                            decision.set_result(accepted)
                            page.pop_dialog()

                    request_dialog = ft.AlertDialog(
                        modal=True,
                        title=ft.Text("طلب استقبال ملف"),
                        content=ft.Text(
                            f"الجهاز: {source_ip}\nالملف: {filename}\n"
                            f"الحجم: {filesize / (1024 * 1024):.2f} MB"
                        ),
                        actions=[
                            ft.Button(
                                "استقبال",
                                icon=ft.Icons.CHECK,
                                on_click=lambda _: answer(True),
                            ),
                            ft.OutlinedButton(
                                "رفض",
                                icon=ft.Icons.CLOSE,
                                on_click=lambda _: answer(False),
                            ),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    page.show_dialog(request_dialog)

                    try:
                        accepted = await asyncio.wait_for(decision, timeout=30)
                    except asyncio.TimeoutError:
                        page.pop_dialog()
                        accepted = False

                    if not accepted:
                        writer.write(b"REJECT")
                        await writer.drain()
                        handshake_replied = True
                        add_activity(
                            f"تم رفض استقبال {filename} من {source_ip}.", color="red"
                        )
                        return

                    writer.write(b"ACCEPT")
                    await writer.drain()
                    handshake_replied = True
                    progress_bar.visible = True
                    progress_text.visible = True
                    progress_bar.value = 0
                    progress_text.value = f"استلام {filename}: 0%"
                    page.update()

                    receive_dir = get_receive_dir(app_config)
                    receive_dir.mkdir(parents=True, exist_ok=True)
                    received_path = receive_dir / filename
                    partial_path = received_path.with_name(f".{received_path.name}.{os.urandom(4).hex()}.part")
                    received_bytes = 0
                    last_ui_update = 0.0

                    with partial_path.open("wb") as output_file:
                        if encrypted_transfer:
                            wrapped_key = await reader.readexactly(key_size)
                            wrapped_text = device_private_key.decrypt(
                                wrapped_key,
                                padding.OAEP(
                                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                    algorithm=hashes.SHA256(),
                                    label=None,
                                ),
                            )
                            aes_key = base64.urlsafe_b64decode(wrapped_text)
                            nonce_prefix = await reader.readexactly(
                                4 if encoded_filename else 8
                            )
                            chunk_index = 0
                            while received_bytes < filesize:
                                plain_size = min(CHUNK_SIZE, filesize - received_bytes)
                                encrypted_chunk = await reader.readexactly(plain_size + 16)
                                data = decrypt_file_chunk(aes_key, nonce_prefix, chunk_index, encrypted_chunk)
                                await asyncio.to_thread(output_file.write, data)
                                received_bytes += len(data)
                                chunk_index += 1
                                now = time.monotonic()
                                if now - last_ui_update >= 0.1 or received_bytes == filesize:
                                    progress_bar.value = received_bytes / filesize if filesize else 1
                                    progress_text.value = f"استلام {filename}: {int(progress_bar.value * 100)}%"
                                    page.update()
                                    last_ui_update = now
                        else:
                            while received_bytes < filesize:
                                data = await reader.read(min(CHUNK_SIZE, filesize - received_bytes))
                                if not data:
                                    break
                                await asyncio.to_thread(output_file.write, data)
                                received_bytes += len(data)
                                now = time.monotonic()
                                if now - last_ui_update >= 0.1 or received_bytes == filesize:
                                    progress_bar.value = received_bytes / filesize if filesize else 1
                                    progress_text.value = f"استلام {filename}: {int(progress_bar.value * 100)}%"
                                    page.update()
                                    last_ui_update = now

                    if received_bytes != filesize:
                        partial_path.unlink(missing_ok=True)
                        add_activity(
                            f"انقطع الاتصال أثناء استقبال {filename}.", color="red"
                        )
                        return

                    partial_path.replace(received_path)

                    if encoded_filename:
                        writer.write(b"DONE")
                        await writer.drain()
                    add_activity(
                        f"تم استلام {filename} وحفظه في {received_path}.", color="green"
                    )
                    await play_notification()
                except (OSError, ValueError, asyncio.TimeoutError) as error:
                    if not handshake_replied:
                        try:
                            writer.write(b"REJECT")
                            await writer.drain()
                        except OSError:
                            pass
                    if "partial_path" in locals():
                        partial_path.unlink(missing_ok=True)
                    add_activity(f"تعذر استقبال الملف: {error}", color="red")
                except Exception as error:
                    if not handshake_replied:
                        try:
                            writer.write(b"REJECT")
                            await writer.drain()
                        except OSError:
                            pass
                    if "partial_path" in locals():
                        partial_path.unlink(missing_ok=True)
                    add_activity(f"حدث خطأ أثناء الاستقبال: {error}", color="red")
                finally:
                    progress_bar.visible = False
                    progress_text.visible = False
                    page.update()
        except (OSError, ValueError, UnicodeDecodeError, asyncio.TimeoutError) as error:
            if "prefix" in locals() and prefix == b"FILE":
                try:
                    writer.write(b"REJECT")
                    await writer.drain()
                except OSError:
                    pass
            add_activity(f"تعذر استقبال البيانات: {error}", color="red")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def stop_network():
        """Stop network services and withdraw this device's Zeroconf announcement."""
        old_server = network["server"]
        old_browser = network["browser"]
        old_zeroconf = network["zeroconf"]
        network.update(server=None, browser=None, zeroconf=None, service=None)

        try:
            if old_server is not None:
                old_server.close()
                await old_server.wait_closed()
        finally:
            try:
                if old_browser is not None:
                    await old_browser.async_cancel()
            finally:
                if old_zeroconf is not None:
                    await old_zeroconf.async_close()

    async def restart_network():
        """Restart the TCP listener and Zeroconf announcement with current settings."""
        await stop_network()

        with devices_lock:
            discovered_devices.clear()
        await refresh_devices()

        server = None
        zeroconf = None
        service_info = None
        browser = None
        try:
            server = await asyncio.start_server(
                handle_incoming_file, host="0.0.0.0", port=app_config["port"]
            )
            local_ip = get_local_ip()
            zeroconf = AsyncZeroconf()
            service_info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=f"{HOSTNAME}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=app_config["port"],
                properties={"device_name": app_config["device_name"]},
                server=f"{HOSTNAME}.local.",
            )

            class DeviceListener:
                """Keep the shared device list synchronized with mDNS events."""

                def add_service(self, zc, service_type, service_name):
                    asyncio.create_task(
                        self.resolve_service(zc, service_type, service_name)
                    )

                async def resolve_service(self, zc, service_type, service_name):
                    info = AsyncServiceInfo(service_type, service_name)
                    try:
                        resolved = await info.async_request(zc, timeout=3000)
                    except (OSError, asyncio.TimeoutError):
                        return
                    if not resolved:
                        return
                    addresses = [
                        socket.inet_ntoa(address)
                        for address in info.addresses
                        if len(address) == 4
                    ]
                    if not addresses or local_ip in addresses:
                        return
                    device_name = info.properties.get(
                        b"device_name", b"Unknown"
                    ).decode("utf-8", errors="replace")
                    with devices_lock:
                        discovered_devices[service_name] = {
                            "id": service_name,
                            "name": device_name,
                            "ip": addresses[0],
                            "port": info.port,
                        }
                    schedule_device_refresh()

                def remove_service(self, zc, service_type, service_name):
                    with devices_lock:
                        discovered_devices.pop(service_name, None)
                    schedule_device_refresh()

                def update_service(self, zc, service_type, service_name):
                    self.add_service(zc, service_type, service_name)

            await zeroconf.async_register_service(service_info)
            browser = AsyncServiceBrowser(
                zeroconf.zeroconf, SERVICE_TYPE, DeviceListener()
            )
            network.update(
                server=server,
                zeroconf=zeroconf,
                service=service_info,
                browser=browser,
            )
            network_status_text.value = (
                f"متصل على {local_ip}:{app_config['port']}"
            )
            add_activity("بدأ اكتشاف الأجهزة واستقبال الملفات.", color="green")
        except Exception as error:
            if browser is not None:
                await browser.async_cancel()
            if zeroconf is not None:
                await zeroconf.async_close()
            if server is not None:
                server.close()
                await server.wait_closed()
            network_status_text.value = f"تعذر بدء خدمات الشبكة: {error}"
            add_activity(f"تعذر بدء خدمات الشبكة: {error}", color="red")
        page.update()

    async def monitor_live_speed():
        """Update the displayed upload and download rate from psutil counters."""
        if psutil is None:
            speed_status_text.value = "Live network speed is unavailable on this platform."
            page.update()
            return

        previous = psutil.net_io_counters()
        previous_time = time.monotonic()
        while session["active"]:
            await asyncio.sleep(1)
            if not session["active"]:
                break
            current = psutil.net_io_counters()
            current_time = time.monotonic()
            elapsed = max(current_time - previous_time, 0.001)
            upload = max(0, current.bytes_sent - previous.bytes_sent) / elapsed
            download = max(0, current.bytes_recv - previous.bytes_recv) / elapsed
            speed_status_text.value = (
                f"رفع: {format_speed(upload)} | تحميل: {format_speed(download)}"
            )
            page.update()
            previous = current
            previous_time = current_time

    def release_android_network_locks():
        while android_network_locks:
            lock = android_network_locks.pop()
            try:
                if lock.isHeld():
                    lock.release()
            except Exception as error:
                print(f"تعذر تحرير قفل شبكة Android: {error}")

    async def stop_session(_):
        session["active"] = False
        try:
            await stop_network()
        finally:
            release_android_network_locks()

    def keep_android_network_active():
        """Hold Wi-Fi, multicast, and CPU locks while this Android session runs."""
        if page.platform != ft.PagePlatform.ANDROID:
            return

        try:
            context, autoclass = get_android_context()
            wifi_manager = context.getSystemService("wifi")
            power_manager = context.getSystemService("power")

            wifi_lock = wifi_manager.createWifiLock(
                wifi_manager.WIFI_MODE_FULL_HIGH_PERF,
                "LocalSend::WiFi",
            )
            wifi_lock.setReferenceCounted(False)
            wifi_lock.acquire()
            android_network_locks.append(wifi_lock)

            multicast_lock = wifi_manager.createMulticastLock(
                "LocalSend::Multicast"
            )
            multicast_lock.setReferenceCounted(False)
            multicast_lock.acquire()
            android_network_locks.append(multicast_lock)

            power_manager_class = autoclass("android.os.PowerManager")
            wake_lock = power_manager.newWakeLock(
                power_manager_class.PARTIAL_WAKE_LOCK,
                "LocalSend::Network",
            )
            wake_lock.setReferenceCounted(False)
            wake_lock.acquire()
            android_network_locks.append(wake_lock)
            add_activity(
                "سيبقى اكتشاف الأجهزة نشطًا عند إطفاء الشاشة؛ قد يزيد ذلك استهلاك البطارية.",
                color="green",
            )
        except Exception as error:
            release_android_network_locks()
            add_activity(
                f"تعذر إبقاء الشبكة نشطة عند إطفاء الشاشة: {error}",
                color="red",
            )

    async def handle_page_disconnect(_):
        """Keep Android network services alive if the UI connection drops temporarily."""
        if page.platform != ft.PagePlatform.ANDROID:
            await stop_session(None)

    async def handle_app_lifecycle_state_change(e: ft.AppLifecycleStateChangeEvent):
        if e.state == ft.AppLifecycleState.DETACH:
            await stop_session(e)

    async def send_text_message(_):
        """Send a UTF-8 text message to the selected discovered device."""
        message = message_input.value or ""
        if not message:
            return

        target_id = message_device_dropdown.value
        with devices_lock:
            target = next(
                (
                    device.copy()
                    for device in discovered_devices.values()
                    if device["id"] == target_id
                ),
                None,
            )
        if target is None:
            add_activity("اختر جهازًا متصلًا لإرسال الرسالة.", color="red")
            return

        payload = message.encode("utf-8")
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target["ip"], target["port"]), timeout=15
            )
            writer.write(b"KEY?")
            await writer.drain()
            public_size = int.from_bytes(await asyncio.wait_for(reader.readexactly(4), timeout=10), "big")
            if not 1 <= public_size <= 8192:
                raise ValueError("Invalid receiver public key")
            receiver_public_key = serialization.load_pem_public_key(
                await asyncio.wait_for(reader.readexactly(public_size), timeout=10)
            )
            writer.close()
            await writer.wait_closed()
            writer = None

            aes_key = os.urandom(32)
            nonce_prefix = os.urandom(4)
            wrapped_key = encrypt_message(
                receiver_public_key, base64.urlsafe_b64encode(aes_key).decode("ascii")
            )
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target["ip"], target["port"]), timeout=15
            )
            writer.write(
                f"MSGC:{len(payload)}:{len(wrapped_key)}\n".encode("ascii")
                + wrapped_key + nonce_prefix
            )
            await writer.drain()
            for chunk_index, offset in enumerate(range(0, len(payload), CHUNK_SIZE)):
                chunk = payload[offset : offset + CHUNK_SIZE]
                writer.write(encrypt_file_chunk(aes_key, nonce_prefix, chunk_index, chunk))
                await writer.drain()
            acknowledgement = await asyncio.wait_for(
                reader.readexactly(2), timeout=10
            )
            if acknowledgement != b"OK":
                raise OSError("لم يؤكد الجهاز استلام الرسالة.")

            add_activity(f"إلى {target['name']}: {message}", is_me=True)
            message_input.value = ""
            page.update()
        except Exception as error:
            add_activity(f"تعذر إرسال الرسالة: {error}", color="red")
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    async def send_file_to_device(selected_file, target):
        """Send one selected file to a discovered device using the TCP protocol."""
        raw_path = getattr(selected_file, "path", None)
        if raw_path is None and callable(
            getattr(selected_file, "getAbsolutePath", None)
        ):
            raw_path = selected_file
        file_path = local_file_path(raw_path)
        file_handle = None
        writer = None
        file_bytes = getattr(selected_file, "bytes", None)
        name_value = getattr(selected_file, "name", None)
        if name_value is None:
            name_value = selected_file
        if not isinstance(name_value, str):
            get_name = getattr(name_value, "getName", None)
            name_value = get_name() if callable(get_name) else str(name_value)
        filename = Path(str(name_value)).name.replace("\r", "_").replace("\n", "_")

        try:
            if file_path:
                try:
                    file_handle = open(file_path, "rb")
                except (OSError, TypeError):
                    if file_bytes is None:
                        raise
            if file_handle is not None:
                file_handle.seek(0, os.SEEK_END)
                filesize = file_handle.tell()
                file_handle.seek(0)
            elif file_bytes is not None:
                filesize = len(file_bytes)
            else:
                raise OSError("لم يوفّر منتقي الملفات مسارًا محليًا قابلًا للقراءة.")
            if not filename:
                filename = "file"

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target["ip"], target["port"]), timeout=15
            )
            writer.write(b"KEY?")
            await writer.drain()
            public_size = int.from_bytes(await asyncio.wait_for(reader.readexactly(4), timeout=10), "big")
            if not 1 <= public_size <= 8192:
                raise ValueError("Invalid receiver public key")
            receiver_public_key = serialization.load_pem_public_key(
                await asyncio.wait_for(reader.readexactly(public_size), timeout=10)
            )
            # The receiver closes the KEY? connection after returning its key.
            # Reconnect before requesting file approval and transferring bytes.
            writer.close()
            await writer.wait_closed()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target["ip"], target["port"]), timeout=15
            )
            aes_key = os.urandom(32)
            # Keep the established FILEE header so already-installed receivers
            # continue to show the incoming-file approval dialog.
            nonce_prefix = os.urandom(8)
            wrapped_key = encrypt_message(
                receiver_public_key, base64.urlsafe_b64encode(aes_key).decode("ascii")
            )
            writer.write(f"FILEE:{filename}:{filesize}:{len(wrapped_key)}\n".encode("utf-8"))
            await writer.drain()
            try:
                response = await asyncio.wait_for(reader.readexactly(6), timeout=35)
            except asyncio.IncompleteReadError as error:
                raise OSError(
                    "أغلق جهاز الاستقبال الاتصال قبل قبول الملف. أعد المحاولة وتأكد من أن التطبيق مفتوح على الجهاز الآخر."
                ) from error
            if response != b"ACCEPT":
                add_activity(f"رفض {target['name']} استقبال {filename}.", color="red")
                return

            writer.write(wrapped_key + nonce_prefix)
            await writer.drain()
            progress_bar.visible = True
            progress_text.visible = True
            progress_bar.value = 0
            progress_text.value = f"إرسال {filename}: 0%"
            page.update()

            sent_bytes = 0
            last_ui_update = 0.0
            while sent_bytes < filesize:
                if file_handle is not None:
                    data = await asyncio.to_thread(file_handle.read, CHUNK_SIZE)
                else:
                    data = file_bytes[sent_bytes : sent_bytes + CHUNK_SIZE]
                if not data:
                    break
                encrypted_data = encrypt_file_chunk(aes_key, nonce_prefix, sent_bytes // CHUNK_SIZE, data)
                writer.write(encrypted_data)
                await writer.drain()
                sent_bytes += len(data)
                now = time.monotonic()
                if now - last_ui_update >= 0.1 or sent_bytes == filesize:
                    progress_bar.value = sent_bytes / filesize if filesize else 1
                    progress_text.value = (
                        f"إرسال {filename}: {int(progress_bar.value * 100)}%"
                    )
                    page.update()
                    last_ui_update = now

            if sent_bytes != filesize:
                raise OSError("لم يتم إرسال الملف كاملًا.")
            add_activity(f"تم إرسال {filename} إلى {target['name']} بنجاح.", is_me=True)
        except Exception as error:
            add_activity(f"تعذر إرسال الملف: {error}", color="red")
        finally:
            if file_handle is not None:
                file_handle.close()
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
            progress_bar.visible = False
            progress_text.visible = False
            page.update()

    async def handle_selected_file(selected_file):
        """Choose a discovered recipient for a file selected by the user."""
        with devices_lock:
            devices = list(discovered_devices.values())
        if not devices:
            add_activity("لم يتم اكتشاف أي جهاز لإرسال الملف إليه.", color="red")
            return

        options = [
            ft.dropdown.Option(
                key=f"{index}",
                text=f"{device['name']} ({device['ip']})",
            )
            for index, device in enumerate(devices)
        ]
        device_dropdown = ft.Dropdown(
            label="جهاز الاستقبال",
            options=options,
            value=options[0].key,
        )

        def close_selector(_):
            page.pop_dialog()

        def confirm_send(_):
            target = devices[int(device_dropdown.value)]
            page.pop_dialog()
            page.run_task(send_file_to_device, selected_file, target)

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("اختر جهاز الاستقبال"),
                content=ft.Column([device_dropdown], height=85, tight=True),
                actions=[
                    ft.Button(
                        "إرسال",
                        icon=ft.Icons.SEND_ROUNDED,
                        on_click=confirm_send
                    ),
                    ft.OutlinedButton("إلغاء", on_click=close_selector),
                ],
            )
        )

    async def pick_file(_):
        """Pick a file from a native desktop or mobile file dialog."""
        selected_files = await file_picker.pick_files(
            allow_multiple=False, with_data=False
        )
        if selected_files:
            await handle_selected_file(selected_files[0])

    def handle_file_result(event: ft.FilePickerResultEvent):
        """Continue after a browser-side PickFiles action returns its selection."""
        if event.files:
            page.run_task(handle_selected_file, event.files[0])

    def handle_directory_result(event: ft.FilePickerResultEvent):
        """Persist a user-chosen receive directory for Android and desktop."""
        if event.path:
            app_config["receive_dir"] = str(safe_receive_dir(event.path))
            app_config["receive_dir_mode"] = "custom"
            save_app_settings(app_config)
            add_activity(f"تم تعيين مجلد الاستلام: {app_config['receive_dir']}", color="green")

    async def pick_receive_directory(_):
        """Pick a destination folder using the OS-supported directory chooser."""
        if hasattr(file_picker, "get_directory_path"):
            selected = await file_picker.get_directory_path()
            if selected:
                app_config["receive_dir"] = str(safe_receive_dir(selected))
                app_config["receive_dir_mode"] = "custom"
                save_app_settings(app_config)
                add_activity(f"تم تعيين مجلد الاستلام: {app_config['receive_dir']}", color="green")
                return
        open_receive_directory(page, app_config)

    async def open_settings(_):
        """Show device name, transfer port, and theme settings."""
        name_input = ft.TextField(
            label="اسم الجهاز على الشبكة", value=app_config["device_name"]
        )
        port_input = ft.TextField(
            label="منفذ TCP", value=str(app_config["port"])
        )
        theme_dropdown = ft.Dropdown(
            label="مظهر التطبيق",
            value=app_config["theme"],
            options=[
                ft.dropdown.Option("system", "حسب النظام"),
                ft.dropdown.Option("dark", "داكن"),
                ft.dropdown.Option("light", "فاتح"),
            ],
        )
        receive_dir_input = ft.TextField(
            label="مسار مجلد الاستلام",
            value=app_config.get("receive_dir") or str(get_received_files_dir()),
            hint_text="مثال: C:/Users/Name/Downloads أو /home/user/Downloads",
            expand=True,
            max_lines=1,
        )

        async def choose_directory_from_browser(_):
            selected = (
                await file_picker.get_directory_path()
                if hasattr(file_picker, "get_directory_path")
                else None
            )
            if selected:
                receive_dir_input.value = selected
                page.update()

        async def save_settings(_):
            try:
                new_port = int(port_input.value)
                if not 1 <= new_port <= 65535:
                    raise ValueError
            except (TypeError, ValueError):
                add_activity("أدخل رقم منفذ صحيحًا بين 1 و65535.", color="red")
                return

            custom_dir = (receive_dir_input.value or "").strip()
            if custom_dir:
                safe_dir = safe_receive_dir(custom_dir)
                app_config["receive_dir"] = str(safe_dir)
                app_config["receive_dir_mode"] = "custom" if str(safe_dir) != str(get_received_files_dir()) else "downloads"
            else:
                app_config["receive_dir"] = str(get_received_files_dir())
                app_config["receive_dir_mode"] = "downloads"

            app_config["device_name"] = name_input.value.strip() or f"Device_{HOSTNAME}"
            app_config["port"] = new_port
            app_config["theme"] = theme_dropdown.value
            try:
                save_app_settings(app_config)
            except (OSError, sqlite3.Error) as error:
                add_activity(f"تعذر حفظ الإعدادات: {error}", color="red")
                return
            page.pop_dialog()
            apply_theme(app_config["theme"])
            await restart_network()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Row(
                    [ft.Icon(ft.Icons.SETTINGS), ft.Text("الإعدادات")], spacing=8
                ),
                content=ft.Column(
                    [
                        name_input,
                        port_input,
                        theme_dropdown,
                        ft.Row(
                            [
                                ft.Container(
                                    content=receive_dir_input,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                                    tooltip="اختيار مجلد الحفظ",
                                    on_click=choose_directory_from_browser,
                                    width=42,
                                    height=42,
                                ),
                            ],
                            spacing=8,
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    height=320,
                    tight=True,
                ),
                actions=[
                    ft.Button("حفظ", icon=ft.Icons.SAVE, on_click=save_settings),
                    ft.OutlinedButton(
                        "إلغاء", on_click=lambda _: page.pop_dialog()
                    ),
                ],
            )
        )

    file_picker = ft.FilePicker(on_result=handle_file_result)
    directory_picker = ft.FilePicker(on_result=handle_directory_result)
    page.services.append(file_picker)
    page.services.append(directory_picker)
    pick_files_action = (
        ft.PickFiles(file_picker, allow_multiple=False, with_data=True)
        if page.web
        else None
    )
    apply_theme(app_config["theme"])

    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS_ROUNDED,
        tooltip="الإعدادات",
        on_click=open_settings,
    )
    file_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        icon_color=ft.Colors.BLUE,
        tooltip="اختيار ملف للإرسال",
        on_click=None if pick_files_action else pick_file,
        action=pick_files_action,
    )
    open_receive_folder_button = ft.IconButton(
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        icon_color=ft.Colors.GREEN,
        tooltip="فتح مجلد استقبال الملفات",
        on_click=pick_receive_directory,
    )

    page.add(
        ft.Container(padding=12,
            content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.WIFI_TETHERING, color=ft.Colors.GREEN),
                                ft.Text("LocalSend Pro", weight=ft.FontWeight.BOLD, size=16),
                            ],
                            spacing=8,
                        ),
                        settings_button,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        ),
        network_status_text,
        ft.Text("الاجهزة المكتشفة ", size=12, weight=ft.FontWeight.BOLD,rtl=True),
        ft.GestureDetector(
            content=devices_list,
            on_scroll=handle_mouse_scroll,
        ),
        ft.Divider(height=1),
        ft.Text("النشاط", size=12, weight=ft.FontWeight.BOLD,rtl=True),
        chat_list,
        ft.Row(
            [
                message_device_dropdown,
                message_input,
                ft.IconButton(
                    icon=ft.Icons.SEND_ROUNDED,
                    tooltip="إرسال رسالة",
                    on_click=send_text_message,
                rtl=True),
            ],
            spacing=6,
        ),
        ft.Column(
            [speed_status_text, progress_text, progress_bar], spacing=3
        ),
        ft.Row(
            [
                file_button,
                open_receive_folder_button,
                ft.Text("إرسال / استقبال الملفات", expand=True, rtl=True),
            ]
        ),
    )

    page.on_disconnect = handle_page_disconnect
    page.on_close = stop_session
    page.on_app_lifecycle_state_change = handle_app_lifecycle_state_change
    keep_android_network_active()
    page.run_task(restart_network)
    page.run_task(monitor_live_speed)


if __name__ == "__main__":
    ft.run(main , assets_dir="assets")

