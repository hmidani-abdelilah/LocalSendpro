"""
================================================================================
ملف وحدة التشفير الهجين (Hybrid Cryptography Module)
--------------------------------------------------------------------------------
الفكرة الأساسية:
1. استخدام RSA (تشفير غير متماثل) لتشفير "مفتاح سري مؤقت" فقط، ولإنشاء هوية دائمة للجهاز.
2. استخدام Fernet / AES (تشفير متماثل سريع) لتشفير الملفات الضخمة مهما بلغ حجمها.
================================================================================
"""

import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet


# ==============================================================================
# القسم الأول: إدارة مفاتيح RSA (هوية الجهاز الدائمة وثابتة الصلاحية)
# ==============================================================================

def generate_keys():
    """
    توليد زوج مفاتيح RSA جديد (خاص + عام) بطول 2048 بت.
    - public_exponent=65537: القيمة القياسية الموصى بها عالمياً للأمان والكفاءة.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()
    return private_key, public_key


def save_keys(private_key, public_key, priv_path="private_key.pem", pub_path="public_key.pem"):
    """
    حفظ المفاتيح في ملفات محلية (PEM Format).
    - الغاية: حفظها مرة واحدة لكي لا يضطر المعالج لإعادة توليدها في كل مرة يُفتح فيها التطبيق (لتجنب إجهاد CPU).
    """
    # حفظ المفتاح الخاص (سري للغاية ولا يغادر الجهاز أبداً)
    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # حفظ المفتاح العام (يمكن مشاركته بحرية مع الأجهزة الأخرى على الشبكة)
    with open(pub_path, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))


def load_private_key(priv_path="private_key.pem"):
    """قراءة وتحميل المفتاح الخاص من القرص الصلب."""
    with open(priv_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key(pub_path="public_key.pem"):
    """قراءة وتحميل المفتاح العام من القرص الصلب."""
    with open(pub_path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


# ==============================================================================
# القسم الثاني: تشفير وفك تشفير الرسائل والبيانات القصيرة (عبر RSA)
# ==============================================================================

def encrypt_message(public_key, message: str) -> bytes:
    """
    تشفير النصوص القصيرة أو "مفاتيح الجلسة" باستخدام المفتاح العام للطرف الآخر.
    - يُستخدم نظام الحشو OAEP مع خوارزمية SHA256 لضمان أعلى معايير الحماية الحديثة.
    """
    return public_key.encrypt(
        message.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def decrypt_message(private_key, encrypted_message: bytes) -> str:
    """
    فك تشفير البيانات الواردة (مثل مفتاح الجلسة المشفر) باستخدام مفتاحك الخاص حصراً.
    """
    decrypted = private_key.decrypt(
        encrypted_message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return decrypted.decode()


# ==============================================================================
# القسم الثالث: التشفير الهجين للملفات (دمج سرعة Fernet وأمان RSA)
# ==============================================================================

def prepare_encrypted_file(file_path: str, receiver_public_key) -> tuple:
    """
    تُستخدم من قبل (المرسل) لتجهيز الملف قبل إرساله عبر الشبكة:
    1. توليد مفتاح سري عشوائي مؤقت (Session Key) لتشفير الملف بسرعة.
    2. تشفير محتوى الملف بالكامل باستخدام خوارزمية Fernet (مهما كان حجم الملف كبيرأً).
    3. تشفير مفتاح الجلسة نفسه باستخدام المفتاح العام للطرف المستقبل (RSA) لضمان عدم سرقته.

    النتيجة المُرجعة: (مفتاح الجلسة المشفر بـ RSA, بيانات الملف المشفرة بـ Fernet)
    """
    # أ) توليد مفتاح سري عشوائي خاص بهذا الملف فقط
    session_key = Fernet.generate_key()
    fernet_cipher = Fernet(session_key)

    # ب) قراءة الملف الحقيقي من القرص وتشفير محتوياته بالكامل
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    encrypted_file_bytes = fernet_cipher.encrypt(file_bytes)

    # ج) تشفير مفتاح الجلسة بالمفتاح العام للطرف الآخر لضمان أمان انتقاله
    encrypted_session_key = encrypt_message(receiver_public_key, session_key.decode())

    return encrypted_session_key, encrypted_file_bytes


def save_decrypted_file(encrypted_session_key: bytes, encrypted_file_bytes: bytes, my_private_key, output_path: str):
    """
    تُستخدم من قبل (المستقبل) لاستلام وفك تشفير الملف الوارد:
    1. فك تشفير مفتاح الجلسة باستخدام مفتاحك الخاص (RSA Private Key).
    2. استخدام مفتاح الجلسة المستخرج لفك تشفير بيانات الملف الحقيقية (Fernet).
    3. حفظ الملف الأصلي ونظيفاً في مسار التخزين على جهازك.
    """
    # أ) فك تشفير مفتاح الجلسة باستخدام مفتاحك الخاص
    session_key_str = decrypt_message(my_private_key, encrypted_session_key)
    session_key = session_key_str.encode()

    # ب) بناء مفتاح فك التشفير واستخدامه لاسترجاع الملف الأصلي
    fernet_cipher = Fernet(session_key)
    original_file_bytes = fernet_cipher.decrypt(encrypted_file_bytes)

    # ج) كتابة البيانات المفكوكة وحفظها كملف حقيقي على القرص
    with open(output_path, "wb") as f:
        f.write(original_file_bytes)