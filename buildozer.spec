[app]
title = DownKaze
package.name = downkaze
package.domain = com.kam3ikaze.downkaze

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,bin
version = 1.0

# المتطلبات البرمجية الأساسية لعمل التطبيق والتحميل بأمان داخل أندرويد
requirements = python3,kivy==2.3.0,pyjnius,certifi,yt-dlp

orientation = portrait
fullscreen = 0

# الصلاحيات المطلوبة للتواصل والتحميل للمجلدات العامة
android.permissions = INTERNET, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

android.allow_backup = True
android.private_storage = False
p4a.branch = v2024.01.21

android.release_artifact = apk
android.keystore = 
android.keystore_passwd = 
android.keyalias = 
android.keyalias_passwd = 

[buildozer]
log_level = 2
warn_on_root = 1
