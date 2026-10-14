# LocalSend Pro

تطبيق لمشاركة الملفات والرسائل النصية مباشرةً بين الأجهزة المتصلة بالشبكة المحلية، مع اكتشاف الأجهزة تلقائيًا عبر Zeroconf.

## الميزات

- اكتشاف الأجهزة المتاحة على الشبكة المحلية.
- إرسال الملفات والرسائل النصية إلى جهاز آخر.
- طلب موافقة المستقبِل قبل استقبال الملف.
- اختيار مجلد حفظ الملفات المستلمة.
- عرض حالة الاتصال وسرعة نقل الشبكة.
- دعم بناء التطبيق لأنظمة Linux وWindows وmacOS وAndroid وiOS.

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
