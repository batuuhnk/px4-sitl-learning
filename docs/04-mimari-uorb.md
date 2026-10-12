# 4. PX4 mimarisi: uORB ve modüller

Bu bölümde PX4'ü çalışırken inceledim. Komutları PX4'ün konsolunda (`pxh>`) çalıştırdım. Modüllerin hangi topic'leri yayınladığını da kaynak koddan kontrol ettim.

## Genel şema

PX4'te modüller birbirini doğrudan çağırmıyor. Her modül sonucunu bir uORB topic'ine yayınlıyor, ihtiyacı olan modül de o topic'e abone oluyor. Aşağıdaki şemada kutular modüller, oklar üzerindeki isimler topic'ler. Çok kopterde (multicopter) sensörden motora kadar olan ana veri yolu bu:

```mermaid
flowchart TB
    subgraph SIM["Sensörler (bende simülatör, gerçek araçta sürücüler)"]
        SIH["simulator_sih<br/>fizik modeli + IMU"]
        GPSS["sensor_gps_sim"]
        BAROS["sensor_baro_sim"]
        MAGS["sensor_mag_sim"]
    end

    SENS["sensors<br/>sensör seçimi, filtreleme, kalibrasyon"]
    EKF["ekf2<br/>konum ve duruş tahmini"]

    subgraph KARAR["Karar ve görev"]
        NAV["navigator<br/>görev, RTL, bekleme"]
        CMD["commander<br/>arm, uçuş modu, failsafe"]
        LAND["land_detector"]
    end

    subgraph KONTROL["Kontrol (iç içe döngüler)"]
        FMM["flight_mode_manager"]
        POS["mc_pos_control<br/>konum, 125 Hz"]
        ATT["mc_att_control<br/>duruş, 250 Hz"]
        RATE["mc_rate_control<br/>açısal hız, 250 Hz"]
        ALLOC["control_allocator<br/>tork ve itkiyi motorlara dağıt"]
    end

    OUT["pwm_out_sim<br/>gerçek araçta PWM/DShot sürücüsü"]

    subgraph HAB["Haberleşme ve kayıt"]
        MAV["mavlink"]
        LOG["logger"]
    end
    QGC["QGroundControl"]

    SIH -->|"sensor_accel, sensor_gyro"| SENS
    GPSS -->|sensor_gps| SENS
    BAROS -->|sensor_baro| SENS
    MAGS -->|sensor_mag| SENS
    SENS -->|"vehicle_imu, vehicle_air_data,<br/>vehicle_magnetometer, vehicle_gps_position"| EKF
    SENS -->|vehicle_angular_velocity| RATE
    EKF -->|vehicle_local_position| POS
    EKF -->|vehicle_attitude| ATT
    EKF -->|estimator_status| CMD
    NAV -->|position_setpoint_triplet| FMM
    FMM -->|trajectory_setpoint| POS
    POS -->|vehicle_attitude_setpoint| ATT
    ATT -->|vehicle_rates_setpoint| RATE
    RATE -->|"vehicle_torque_setpoint,<br/>vehicle_thrust_setpoint"| ALLOC
    ALLOC -->|actuator_motors| OUT
    OUT -->|actuator_outputs| SIH
    LAND -->|vehicle_land_detected| CMD
    CMD -->|"vehicle_status,<br/>vehicle_control_mode"| KONTROL
    QGC <-->|"MAVLink, UDP 14550"| MAV
    MAV -->|vehicle_command| CMD
```

`logger` neredeyse bütün topic'lere abone, uçuş boyunca hepsini `.ulg` dosyasına yazıyor. Şemayı kalabalıklaştırmamak için oklarını çizmedim.

### Katman katman modüller

**Sensörler.** Gerçek araçta her sensörün kendi sürücüsü var (örneğin ICM-42688 IMU sürücüsü), `src/drivers/` altında. Bende bunların yerine simülatör modülleri çalışıyor: `simulator_sih` IMU verisini, `sensor_gps_sim`, `sensor_baro_sim` ve `sensor_mag_sim` de GPS, barometre ve manyetometre verisini üretiyor. `simulator_sih` ayrıca aracın gerçek konumunu da `*_groundtruth` topic'lerine yayınlıyor. 5. bölümde EKF2'nin tahminini bununla karşılaştırdım.

**Sensör işleme.** `sensors` modülü birden fazla IMU varsa hangisinin kullanılacağını seçiyor, kalibrasyonu uyguluyor ve veriyi filtreliyor. Kontrolcülerin kullandığı `vehicle_angular_velocity` de burada üretiliyor.

**Tahmin.** `ekf2`, IMU'yu GPS, barometre ve manyetometreyle birleştirip (sensör füzyonu) aracın konumunu, hızını ve duruşunu tahmin ediyor.

**Karar.** `commander` aracın genel durumunu yönetiyor: arm/disarm, uçuş modu, sağlık kontrolleri ve failsafe kararları. `navigator` görev (mission), eve dönüş (RTL) gibi otomatik modlarda hedef noktaları üretiyor. `land_detector` aracın yere inip inmediğini anlıyor.

**Kontrol.** İç içe geçmiş döngüler (kaskad kontrol). Dıştan içe doğru: konum → duruş → açısal hız. Her döngü bir içtekine hedef veriyor ve içteki döngüler daha hızlı çalışıyor. `control_allocator` en sonda istenen tork ve itkiyi dört motora paylaştırıyor.

**Çıkış.** Gerçek araçta motor sürücüleri (ESC) PWM ya da DShot ile sürülüyor. Bende `pwm_out_sim` motor komutlarını simülatöre geri veriyor ve döngü kapanıyor.

**Haberleşme.** `mavlink` QGroundControl ile konuşuyor: telemetriyi gönderiyor, QGC'den gelen komutları (kalkış, mod değiştirme) `vehicle_command` olarak içeri alıyor.

## Thread'ler (task'lar)

Başlangıçta "PX4'te her modül ayrı bir task" diye düşünüyordum. Bu doğru değilmiş.

SITL'de PX4'ün her task'ı bir Linux thread'i olduğu için hepsini Linux'tan listeleyebildim:

```bash
docker exec px4dev bash -c 'for t in /proc/$(pgrep -x px4)/task/*; do cat $t/comm; done'
```

Toplam 28 thread çıktı. Ana `px4` thread'i, `wq:manager` (work queue'ları oluşturan yönetici), `hpwork`, `lpwork` ve `wkr_hrt` (zamanlayıcı işleri) gibi altyapı thread'lerini ayırınca geri kalanlar ikiye ayrılıyor:

**Kendi thread'i olan modüller:**

```
commander               arm, mod, failsafe
navigator               görev ve otomatik modlar
sih                     simülatör
logger, log_writer_file log kaydı (biri toplar, diğeri dosyaya yazar)
mavlink_if0..4          her MAVLink bağlantısı için gönderme thread'i (5 bağlantı)
mavlink_rcv_if0..4      ve alma thread'i
dataman                 görev noktalarını kalıcı olarak saklar
uxrce_dds_client        ROS 2 bağlantısı
```

**Work queue thread'leri.** Geri kalan modüllerin kendi thread'i yok. Ortak bir thread'e "work item" olarak kayıtlılar ve sırası gelince çalışıyorlar. `work_queue status` çıktısı:

```
wq:rate_ctrl            (en yüksek öncelik)
    vehicle_angular_velocity, mc_rate_control, control_allocator, pwm_out_sim
wq:INS0
    vehicle_imu, ekf2
wq:nav_and_controllers
    sensors, mc_att_control, mc_pos_control, flight_mode_manager, land_detector,
    mc_hover_thrust_estimator, vehicle_acceleration, vehicle_air_data,
    vehicle_gps_position, vehicle_magnetometer
wq:hp_default
    sensor_baro_sim, sensor_gps_sim, sensor_mag_sim, battery_simulator, gyro_fft, ...
wq:lp_default
    load_mon, gyro_calibration, parameters, ...
```

Yani yaklaşık 30 modül 5 work queue thread'i üzerinde çalışıyor. Neden böyle olduğunu `wq:rate_ctrl` iyi gösteriyor: gyro verisinden motor komutuna giden zincirin tamamı aynı thread'de. Araya context switch girmeden tek bir 4 ms'lik döngüde bitiyor. Az thread kullanmak, her birine ayrı stack ayırmadığı için RAM'den de tasarruf sağlıyor.

Küçük bir detay: Linux'ta thread adı en fazla 15 karakter olabiliyor. `wq:nav_and_controllers` 22 karakter olduğu için listede kendi adıyla değil `px4` olarak görünüyor.

### Modüller nasıl tetikleniyor?

İki yol var: bir topic'e yeni veri gelince (olay tabanlı) ya da belirli aralıklarla (periyodik). `work_queue status` çıktısında parantez içinde süre yazanlar periyodik çalışanlar.

Kaynak kodda `mc_rate_control` örneği:

- `MulticopterRateControl.cpp`: Kurucuda `WorkItem(MODULE_NAME, px4::wq_configurations::rate_ctrl)` ile `wq:rate_ctrl` thread'ine bağlanıyor.
- `MulticopterRateControl.hpp`: `uORB::SubscriptionCallbackWorkItem _vehicle_angular_velocity_sub` satırı, `vehicle_angular_velocity` yayınlandığında modülün `Run()` fonksiyonunu kuyruğa alıyor. ISR'den `xTaskNotifyGive()` ile bir task'ı uyandırmaya benziyor.
- Thread'lerin öncelik ve stack ayarları `platforms/common/include/px4_platform_common/px4_work_queue/WorkQueueManager.hpp` dosyasında.

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
- Kontrol döngülerinin hızları kademeli: konum 125 Hz, duruş ve açısal hız 250 Hz.

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

Önceki: [3. Kurulum ve komutlar](03-kurulum-ve-komutlar.md) · Sonraki: [5. Kontrol döngüleri ve GPS kaybı](05-kontrol-ve-gps-kaybi.md)
