flet build apk \
  --android-permissions android.permission.ACCESS_NETWORK_STATE=true \
  android.permission.ACCESS_WIFI_STATE=true \
  android.permission.CHANGE_WIFI_MULTICAST_STATE=true

keytool -genkey -v -keystore $env:USERPROFILE\upload-keystore.jks ` -storetype JKS -keyalg RSA -keysize 2048 -validity 10000 ` -alias upload

& "C:\Users\abdelilah\java\17.0.13+11\bin\keytool.exe" -genkey -v -keystore $env:USERPROFILE\upload-keystore.jks -storetype JKS -keyalg RSA -keysize 2048 -validity 10000 -alias upload
