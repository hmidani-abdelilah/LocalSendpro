# LocalSend Pro
<p align="center">
  <img src="https://raw.githubusercontent.com/hmidani-abdelilah/LocalSendpro/refs/heads/main/LocalSendPro-AR.png" alt="LocalSend Pro">
</p>



تطبيق لمشاركة الملفات والرسائل النصية مباشرةً بين الأجهزة المتصلة بالشبكة المحلية، مع اكتشاف الأجهزة تلقائيًا عبر Zeroconf.

**English version:** see the complete translation at [English version](#english-version).

## الميزات

- اكتشاف الأجهزة المتاحة على الشبكة المحلية.
- إرسال الملفات والرسائل النصية إلى جهاز آخر.
- تشفير محتوى الرسائل والملفات أثناء النقل بين الأجهزة.
- طلب موافقة المستقبِل قبل استقبال الملف.
- اختيار مجلد حفظ الملفات المستلمة.
- تغيير لغة الواجهة إلى العربية أو الإنجليزية أو الفرنسية وحفظ الاختيار بين مرات التشغيل.
- عرض حالة الاتصال وسرعة نقل الشبكة.
- تشغيل نغمة عند اكتمال استقبال ملف.
- دعم بناء التطبيق لأنظمة Linux وWindows وmacOS وAndroid وiOS.

## بنية المشروع

```text
LocalSendpro-main/
├── main.py                    # نقطة تشغيل التطبيق والواجهة وخدمات الشبكة
├── crypto_utils.py            # تشفير الرسائل والملفات
├── speed.py                   # أداة مستقلة لعرض سرعة الشبكة
├── localsend_zeroconf.py      # نسخة مساعدة لاكتشاف الأجهزة عبر Zeroconf
├── pyproject.toml             # إعدادات Flet وبناء المنصات
├── requirements.txt           # حزم Python المطلوبة
├── README.md
├── LICENSE
├── LocalSendPro.png           # صورة المشروع
├── notification.wav           # نسخة صوت سطح المكتب
├── assets/
│   ├── notification.wav       # نغمة الإشعار المضمّنة في التطبيق
│   ├── icon*.png              # أيقونات التطبيق
│   └── splash*.png            # صور شاشة البداية
├── test/                      # ملفات تجارب وأدوات تطوير
└── copy code/                 # نسخ قديمة محفوظة من ملفات التطبيق
```

## تنزيل التطبيق

نزّل الإصدار المناسب لجهازك من صفحة [Releases](../../releases). قد تختلف صيغة الملف حسب النظام؛ ملفات Linux وmacOS وWindows وAndroid تُرفق كأرشيفات بناء.

بناء iOS من GitHub Actions قد ينتج ملف `.xcarchive`. يتطلب إنشاء ملف `.ipa` قابلًا للتثبيت إعداد شهادة توقيع Apple وملف Provisioning Profile.

## التشغيل من المصدر

يتطلب Python 3.12 أو أحدث. من مجلد المشروع، أنشئ بيئة افتراضية وثبّت الحزم ثم شغّل التطبيق:

```bash
python -m venv .venv
```

على Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

على Linux أو macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

اسمح للتطبيق بالوصول إلى الشبكة المحلية في إعدادات جدار الحماية. يستخدم التطبيق المنفذ `50006` للاتصال بين الأجهزة.

## التشفير

يشفّر التطبيق محتوى الرسائل والملفات أثناء النقل باستخدام AES-GCM، ويستخدم RSA-OAEP مع SHA-256 لتغليف مفتاح AES وإرساله إلى الجهاز المستقبِل. تُشفّر الملفات على دفعات، لذلك لا يحتاج التطبيق إلى تحميل الملف كاملاً إلى الذاكرة.

يُنشأ مفتاح RSA في ذاكرة التطبيق عند تشغيله ولا يُحفظ على القرص. يتبادل الجهازان المفتاح العام عبر الشبكة المحلية من دون التحقق من بصمته؛ لذلك يحمي التشفير المحتوى من التنصت السلبي، لكنه لا يضمن هوية الجهاز ضد طرف نشط يعترض الاتصال ويستبدل المفتاح. كما تبقى بيانات النقل مثل اسم الملف وحجمه ظاهرة على الشبكة.

يتطلب الإرسال المشفّر تشغيل إصدار متوافق من التطبيق على الجهازين. لا يقبل التطبيق الرسائل أو الملفات الواردة عبر بروتوكول الإصدارات القديمة غير المشفّر.

## حفظ الإعدادات

يحفظ التطبيق اسم الجهاز على الشبكة، ومنفذ TCP، ومظهر التطبيق (النظام أو الفاتح أو الداكن)، ولغة الواجهة، ومجلد حفظ الملفات المستلمة. تتوفر العربية والإنجليزية والفرنسية من **الإعدادات ← اللغة**، ويُحفظ الاختيار تلقائياً ليبقى بعد إعادة تشغيل التطبيق.

تُحفظ الإعدادات في قاعدة SQLite باسم `localsend_settings.sqlite3`. توجد قاعدة البيانات داخل مجلد ملفات التطبيق على Android، وفي `~/.localsendpro/` على الحواسيب.

يستخدم Android مجلد `Download` العام على وحدة التخزين المشتركة. يستخدم Windows مجلد `Downloads` ضمن مجلد المستخدم، ويستخدم macOS مجلد `~/Downloads`. على Linux، يتبع التطبيق مجلد التنزيلات المحدد في إعدادات XDG إن وُجد، وإلا يستخدم `~/Downloads`. يمكن تغيير مجلد الحفظ من الإعدادات.

## إنشاء إصدار وتنزيلاته تلقائيًا

يبدأ GitHub Actions بناء جميع المنصات وينشر الملفات في صفحة Releases عند دفع وسم إصدار بصيغة `vX.Y.Z` إلى GitHub. مثال:

```bash
git tag v1.0.1
git push origin v1.0.1
```

تأكد من نجاح وظائف البناء في تبويب **Actions**؛ بعد اكتمالها، سيظهر الإصدار وملفاته في **Releases**.

## التقنيات

- [Flet](https://flet.dev/) لواجهة التطبيق والبناء متعدد المنصات.
- [Zeroconf](https://github.com/python-zeroconf/python-zeroconf) لاكتشاف الأجهزة على الشبكة المحلية.

## الترخيص

هذا المشروع مرخّص بموجب [GNU Affero General Public License v3.0](LICENSE).

---

# English version

<p align="center">
  <img src="https://raw.githubusercontent.com/hmidani-abdelilah/LocalSendpro/refs/heads/main/LocalSendPro-EN.png" alt="LocalSend Pro">
</p>

LocalSend Pro lets you share files and text messages directly between devices connected to the same local network. It discovers nearby devices automatically using Zeroconf.

## Features

- Discover available devices on the local network.
- Send files and text messages to another device.
- Encrypt message and file contents while they are being transferred.
- Ask the recipient to approve each incoming file.
- Choose where received files are saved.
- Change the interface language to Arabic, English, or French; the selection is saved between sessions.
- View connection status and network transfer speed.
- Play a sound when a file has been received.
- Build for Linux, Windows, macOS, Android, and iOS.

## Project structure

```text
LocalSendpro-main/
├── main.py                    # App entry point, interface, and network services
├── crypto_utils.py            # Message and file encryption
├── speed.py                   # Standalone network speed utility
├── localsend_zeroconf.py      # Helper version using Zeroconf discovery
├── pyproject.toml             # Flet and platform build configuration
├── requirements.txt           # Required Python packages
├── README.md
├── LICENSE
├── LocalSendPro.png           # Project image
├── notification.wav           # Desktop notification sound
├── assets/
│   ├── notification.wav       # Notification sound bundled with the app
│   ├── icon*.png              # App icons
│   └── splash*.png            # Splash screen images
├── test/                      # Development and experiment files
└── copy code/                 # Older copies of application files
```

## Download

Download the build for your device from the [Releases](../../releases) page. The attached file format may vary by platform; Linux, macOS, Windows, and Android builds are published as build archives.

A GitHub Actions iOS build may produce an `.xcarchive`. Creating an installable `.ipa` requires an Apple signing certificate and a Provisioning Profile.

## Run from source

Python 3.12 or newer is required. From the project directory, create a virtual environment, install the dependencies, and run the app:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

On Linux or macOS:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Allow the app to access the local network in your firewall settings. The app uses TCP port `50006` for device-to-device connections.

## Encryption

The app encrypts message and file contents in transit with AES-GCM. It uses RSA-OAEP with SHA-256 to wrap the AES key and send it to the receiving device. Files are encrypted in chunks, so the entire file does not need to be loaded into memory.

An RSA key pair is generated in memory when the app starts and is not saved to disk. Devices exchange public keys over the local network without verifying their fingerprints. Encryption therefore protects content from passive eavesdropping, but it does not authenticate a device against an active attacker who intercepts the connection and replaces the key. Transfer metadata such as file names and sizes remains visible on the network.

Both devices must run a compatible app version for encrypted transfers. The app rejects incoming messages and files that use the old unencrypted protocol.

## Settings and received files

The app saves the network device name, TCP port, app theme (system, light, or dark), interface language, and receive folder. Arabic, English, and French are available under **Settings → Language**. The selected language is retained after the app is restarted.

Settings are stored in a SQLite database named `localsend_settings.sqlite3`. On Android, the database is stored in the app's files directory. On desktop systems, it is stored under `~/.localsendpro/`.

Android uses the shared `Download` folder. Windows uses the user's `Downloads` folder, and macOS uses `~/Downloads`. On Linux, the app uses the download folder configured through XDG when available, otherwise it uses `~/Downloads`. You can change the receive folder in Settings.

## Automated release builds

GitHub Actions builds the supported platforms and publishes the artifacts to Releases when a version tag in the form `vX.Y.Z` is pushed to GitHub. For example:

```bash
git tag v1.0.1
git push origin v1.0.1
```

Check that the build jobs succeed in the **Actions** tab. When they finish, the release and its artifacts will appear under **Releases**.

## Technology

- [Flet](https://flet.dev/) for the user interface and cross-platform builds.
- [Zeroconf](https://github.com/python-zeroconf/python-zeroconf) for discovering devices on the local network.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).
