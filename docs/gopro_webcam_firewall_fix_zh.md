# GoPro Webcam 防火牆錯誤修復紀錄

日期：2026-06-05

## 目前判斷

GoPro 端設定是正確的：

```text
連線 → USB 連線 → GoPro Connect
```

官方 HERO9 手冊說明：

- `GoPro Connect` 用於將 HERO9 Black 設定為 webcam。
- `MTP` 用於將媒體傳輸到電腦。

目前錯誤通知：

```text
相機網路錯誤
請確保防火牆或代理伺服器未封鎖 GoPro 網路攝影機應用程式存取區域網路
```

這表示 GoPro Webcam app 透過 USB 網路介面連接 GoPro，但 Windows 防火牆、網路分類或代理設定阻擋了 GoPro Webcam app 的區域網路存取。

## 本機檢查結果

GoPro Webcam 程式路徑：

```text
C:\Program Files (x86)\GoPro\GoPro Webcam\GoPro Webcam.exe
```

GoPro USB 網卡：

```text
Name: 乙太網路 3
InterfaceDescription: GoPro RNDIS Device
NetworkCategory: Public
Laptop IP: 172.26.181.54
GoPro IP: 172.26.181.51
```

Proxy 狀態：

```text
WinHTTP proxy: Direct access
User proxy: disabled
```

已存在的防火牆規則：

```text
GoPro Webcam inbound allow, Private/Public
```

但目前缺少明確的 outbound allow 規則，且 GoPro RNDIS 網路仍被分類成 Public。

## 修復腳本

以系統管理員身分開啟 PowerShell，執行：

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\fix_gopro_firewall_admin.ps1
```

腳本會做三件事：

1. 對 `GoPro Webcam.exe` 建立 inbound allow。
2. 對 `GoPro Webcam.exe` 建立 outbound allow。
3. 嘗試將 GoPro RNDIS 網路分類改成 Private。

## 執行後測試

1. 關閉 GoPro Webcam app。
2. 拔掉 GoPro USB。
3. 重新插上 GoPro USB。
4. 開啟 GoPro Webcam app。
5. 在 GoPro Webcam app 中開 Preview。
6. 確認 Preview 能看到真實鏡頭畫面。

如果 GoPro Webcam app 的 Preview 能看到真實畫面，再執行：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\scan_cameras.py --max-index 8 --out-dir .\runs\camera_scan
```

接著用 GoPro 的 camera index 錄測試影片。

## 手動修復路徑

若腳本無法執行，可手動設定：

1. Windows 搜尋 `允許應用程式通過 Windows Defender 防火牆`。
2. 點 `變更設定`。
3. 找 `GoPro Webcam`。
4. 勾選 `私人` 與 `公用`。
5. 若沒有 GoPro Webcam，新增：

```text
C:\Program Files (x86)\GoPro\GoPro Webcam\GoPro Webcam.exe
```

也建議到 Windows 防火牆進階設定中，替此 exe 新增 outbound allow 規則。

## 重新安裝路徑

若 GoPro Webcam app 啟動後沒有系統匣 icon，並且 Windows Event Log 顯示 `GoPro Webcam.exe` crash，可使用重新安裝腳本。

以系統管理員身分開啟 PowerShell：

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\reinstall_gopro_webcam_admin.ps1
```

此腳本會：

1. 停止 GoPro Webcam process。
2. 備份 user state。
3. 解除安裝 GoPro Webcam。
4. 使用 Downloads 裡的 MSI 重新安裝。
5. 重新套用防火牆 inbound/outbound allow。
6. 嘗試將 GoPro RNDIS 網路設定成 Private。
7. 啟動 GoPro Webcam 並檢查最近 crash event。

## 繞過 GoPro Webcam App 的 UDP 擷取路徑

若 GoPro Webcam app 仍持續 crash，可不依賴 tray app，直接呼叫 GoPro 本體 endpoint：

```text
/gp/gpWebcam/START?res=720p
/gp/gpWebcam/KEEP_ALIVE
/gp/gpWebcam/STOP
```

然後使用 FFmpeg 從本機 UDP 8554 接收串流。

若 FFmpeg 收不到封包，先以系統管理員身分執行：

```powershell
cd C:\Users\Douglas\Documents\Codex\2026-06-04\gopro9\outputs\edge-adaptive-video-framework
.\scripts\fix_gopro_udp_capture_admin.ps1
```

再測試：

```powershell
& C:\Users\Douglas\anaconda3\envs\edge_cpu\python.exe .\scripts\capture_gopro_ffmpeg_sample.py --gopro-ip 172.26.181.51 --seconds 8 --res 720p --out .\runs\gopro_udp_test\gopro_ffmpeg_sample.mp4
```

## 參考資料

- GoPro HERO9 Black User Manual: USB Connection 說明 `GoPro Connect` 與 `MTP` 的用途。
- GoPro Open GoPro: HERO9 支援 Open GoPro，包含 USB/Wi-Fi/BLE 控制與狀態查詢。
