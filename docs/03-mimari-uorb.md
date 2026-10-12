# 3. PX4 mimarisi: uORB ve modüller

Bu bölümde PX4'ü çalışırken inceledim. Komutları PX4'ün konsolunda (`pxh>`) çalıştırdım, araç yerdeyken.

## uORB trafiği

`uorb top -1` komutu her topic'in ne sıklıkla yayınlandığını ve kaç modülün dinlediğini gösteriyor. Öne çıkanlar:

| Topic | Hız | Abone sayısı | Kuyruk |
|---|---|---|---|
| `sensor_gyro`, `sensor_accel` | 250 Hz | 6, 5 | 8 |
| `vehicle_attitude` | 250 Hz | 19 | 1 |
| `vehicle_local_position` | 125 Hz | 41 | 1 |
| `vehicle_rates_setpoint` | 250 Hz | 4 | 1 |
| `actuator_motors` | 250 Hz | 1 | 1 |
| `vehicle_status` | 2 Hz | 61 | 1 |

Fark ettiklerim:

- Çoğu topic'in kuyruk derinliği 1. Yani okuyan modül her zaman sadece en son değeri görüyor, yeni veri eskisinin üzerine yazılıyor. FreeRTOS'taki uzunluğu 1 olan kuyruk ve `xQueueOverwrite()` ile aynı mantık.
- Ham gyro ve ivme verisinin kuyruğu 8. Bunlar filtrelere girdiği için örnek kaybolmaması gerekiyor.
- `vehicle_status` saniyede sadece 2 kez yayınlanıyor ama 61 modül dinliyor. Seyrek değişen ama herkesin bilmesi gereken bir bilgi (arm durumu, uçuş modu).
- Kontrol döngülerinin hızları kademeli: konum 125 Hz, attitude ve rate 250 Hz.

## Modüller ve thread'ler

Başlangıçta "PX4'te her modül ayrı bir task" diye düşünüyordum. `work_queue status` bunun doğru olmadığını gösterdi: yaklaşık 30 modül sadece 6 thread üzerinde çalışıyor.

```
wq:rate_ctrl            (en yüksek öncelik)
  vehicle_angular_velocity -> mc_rate_control -> control_allocator -> pwm_out_sim
wq:INS0
  vehicle_imu -> ekf2
wq:nav_and_controllers
  mc_att_control, mc_pos_control, flight_mode_manager, sensors, ...
wq:hp_default, wq:lp_default
  simülatörler, batarya, yük ölçümü, ...
```

Çoğu modül bir "work item": kendi thread'i yok, ortak bir work queue thread'inde sırası gelince çalışıyor. Gyro verisinden motor komutuna giden zincirin tamamı aynı thread'de olduğu için, araya context switch girmeden tek bir 4 ms'lik döngüde bitiyor.

Modüller iki şekilde tetikleniyor: bir topic'e yeni veri gelince (olay tabanlı) ya da belirli aralıklarla (periyodik). Kaynak kodda örneği `mc_rate_control`:

- `MulticopterRateControl.cpp`: Kurucuda `WorkItem(MODULE_NAME, px4::wq_configurations::rate_ctrl)` ile `wq:rate_ctrl` thread'ine bağlanıyor.
- `MulticopterRateControl.hpp`: `uORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub` satırı, `vehicle_angular_velocity` yayınlandığında modülün `Run()` fonksiyonunu kuyruğa alıyor. ISR'den `xTaskNotifyGive()` ile bir task'ı uyandırmaya benziyor.

`commander`, `navigator`, `mavlink` ve `logger` gibi bazı modüller ise hâlâ kendi task'larına sahip.

## İlk kod değişikliğim

PX4'ün örnek modüllerinden `px4_simple_app`'i inceledim. İvme verisine abone olup ekrana basıyor. Ama aynı zamanda bu ivme değerlerini `vehicle_attitude` topic'ine de yayınlıyor. Oysa bu topic'i EKF2 de yayınlıyor ve attitude kontrolcüsü onu kullanıyor. Bu örnek uçan bir araçta çalıştırılsa kontrolcü yanlış veri alırdı.

Yayınlama kısmını kaldırdım, mesajı değiştirdim, derleyip çalıştırdım:

```
INFO  [px4_simple_app] Merhaba PX4 - ilk modulum!
INFO  [px4_simple_app] Accelerometer:    -0.0780    0.0432   -9.8018
INFO  [px4_simple_app] Accelerometer:    -0.0814   -0.0319   -9.7220
...
```

Z ekseninin -9.8 çıkmasının sebebi: ivmeölçer yerçekimini değil, aracı tutan kuvveti ölçüyor (yerin aracı yukarı itmesi). PX4'te gövde ekseni FRD (ileri, sağ, aşağı) olduğu için yukarı doğru olan bu kuvvet eksi çıkıyor.

Değişiklik: [batuuhnk/PX4-Autopilot@a573d42](https://github.com/batuuhnk/PX4-Autopilot/commit/a573d4298d5792f6698205de961f43782ffa3e36)

Önceki: [2. SITL ve simülatörler](02-sitl-ve-simulatorler.md) · Sonraki: [4. Kontrol döngüleri ve GPS kaybı](04-kontrol-ve-gps-kaybi.md)
