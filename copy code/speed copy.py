import time
import psutil

def format_speed(bytes_per_sec):
    """دالة مساعدة لتنسيق السرعة بذكاء (KB/s أو MB/s)"""
    if bytes_per_sec >= 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
    elif bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.2f} KB/s"
    else:
        return f"{bytes_per_sec:.2f} B/s"

def monitor_live_speed(interval=1.0):
    print(f"[*] بدء مراقبة سرعة الشبكة (تحديث كل {interval} ثانية)... اضغط Ctrl+C للإيقاف.\n")
    
    # 1. أخذ قراءة أولية للعدادات
    last_io = psutil.net_io_counters()
    
    try:
        while True:
            time.sleep(interval)
            
            # 2. أخذ قراءة ثانية بعد مرور الفترة المحددة (interval)
            current_io = psutil.net_io_counters()
            
            # 3. حساب الفارق بين القراءتين
            sent_diff = current_io.bytes_sent - last_io.bytes_sent
            recv_diff = current_io.bytes_recv - last_io.bytes_recv
            
            # 4. حساب السرعة بالبايت في الثانية
            upload_speed = sent_diff / interval
            download_speed = recv_diff / interval
            
            # طباعة السرعة في نفس السطر بشكل تفاعلي
            output = f"\r🚀 رفع (Upload): {format_speed(upload_speed)}   |   📥 تحميل (Download): {format_speed(download_speed)}"
            print(output, end="", flush=True)
            
            # تحديث القراءة السابقة للقفزة القادمة
            last_io = current_io
            
    except KeyboardInterrupt:
        print("\n\n[*] تم إيقاف مراقبة الشبكة.")

if __name__ == '__main__':
    monitor_live_speed(interval=1.0)