# 2. SITL, simülatörler ve QGroundControl

Elimde kart ve drone yok. Bu yüzden her şeyi simülasyonda yaptım.

## SITL ve HITL

**SITL (Software In The Loop):** PX4'ün kaynak kodu ARM için değil, bilgisayarın kendi işlemcisi için derleniyor ve normal bir Linux programı olarak çalışıyor. Gerçek sensörlerin ve motorların yerine bir simülatör var: aracın fiziğini hesaplıyor, sahte sensör verisi üretiyor ve motor komutlarını alıyor.

Önemli nokta: uçuş kodunun kendisi (EKF2, kontrolcüler, failsafe mantığı) gerçek kartta çalışanla aynı. Değişen sadece altındaki katman, yani işletim sistemi ve sürücüler.

| | Gerçek Pixhawk | SITL |
|---|---|---|
| İşlemci | STM32 (ARM) | Bilgisayarın CPU'su (x86) |
| İşletim sistemi | NuttX | Linux |
| Derleme | `make px4_fmu-v6x` | `make px4_sitl` |
| Sensörler, motorlar | Gerçek donanım | Simülatör |

**HITL (Hardware In The Loop):** Firmware gerçek kartta çalışıyor, ama sensör verisi simülatörden geliyor. Kart gerektirdiği için ben kullanmadım.

STM32 tarafından bir benzetme: iş mantığını HAL'dan ayırıp aynı `.c` dosyalarını bilgisayarda gcc ile derlemek, `HAL_I2C_Read()` yerine de sahte değer döndüren bir fonksiyon koymak gibi.

## Simülatörler

PX4 birden fazla simülatörle çalışabiliyor:

- **SIH (Simulation In Hardware):** PX4'ün içinde bir modül olarak çalışıyor, ayrı bir program değil (`src/modules/simulation/simulator_sih`). GPS, barometre ve manyetometre verisini de PX4 içindeki `sensor_gps_sim`, `sensor_baro_sim`, `sensor_mag_sim` modülleri üretiyor. Çok hafif, 3D görüntüsü yok. Ben bunu kullandım, çünkü sanal makinemde 4 GB RAM var.
- **Gazebo:** Asıl önerilen simülatör. 3D görüntü, gerçekçi fizik, kamera ve lidar gibi sensörler var. Karşılığında ağır. Ayrı bir program; PX4 ile arasındaki köprü `gz_bridge` modülü (`src/modules/simulation/gz_bridge`).
- **Gazebo Classic:** Gazebo'nun eski sürümü, hâlâ kodda var ama artık önerilmiyor. PX4 ile MAVLink üzerinden konuşuyor; köprü `simulator_mavlink` modülü (`src/modules/simulation/simulator_mavlink`).
- **jMAVSim:** Java ile yazılmış basit bir simülatör, sadece multikopter için. O da `simulator_mavlink` üzerinden bağlanıyor.
- **FlightGear, JSBSim:** Daha çok sabit kanat uçaklar için.

SIH'in bir eksiğini de bu çalışmada buldum: `failure gps off` komutu SIH'te çalışmıyor (ayrıntılar [5. bölümde](05-kontrol-ve-gps-kaybi.md)).

## QGroundControl (simülatör değil)

İlk başta QGroundControl'ü de simülatör sanıyordum, ama değil. QGC bir **yer kontrol istasyonu** (Ground Control Station). Gerçek bir drone'a bağlanır gibi simülasyondaki PX4'e bağlanıyor:

- Haritada aracın konumu, irtifası, batarya durumu
- Kalkış, iniş, mod değiştirme
- Görev (waypoint) planlama
- Parametreleri okuma ve değiştirme, sensör kalibrasyonu

PX4 ile QGC arasındaki haberleşme **MAVLink** protokolüyle oluyor. Gerçek araçta bu bağlantı telemetri radyosu ya da USB üzerinden olur; SITL'de UDP üzerinden (port 14550).

```
QGroundControl  <--- MAVLink, UDP 14550 --->  PX4 (SITL)  <--- uORB --->  SIH simülatörü
 (yer istasyonu)                               (uçuş yazılımı)              (sahte fizik + sensörler)
```

## Benim kurulumum

- VirtualBox'ta Ubuntu 26.04, 4 çekirdek, 4 GB RAM
- PX4 v1.17.0, kaynaktan derlendi
- Derleme PX4'ün resmi Docker imajında (`px4io/px4-dev`) yapılıyor. PX4'ün kurulum betiği sadece Ubuntu 22.04 ve 24.04'ü destekliyor, 26.04'te bağımlılıklar tutmadı. Kod bilgisayarımda duruyor, container'a bağlanıyor.
- QGroundControl (AppImage)

Kurulumda karşılaştığım bir sorun: PX4'ü Docker'da `-p 14550:14550/udp` ile başlattığımda QGC hiç bağlanmadı. Sebebi, docker-proxy'nin host'taki 14550 portunu kendisi tutması ve QGC'nin o portu açamaması. `--network host` ile çözdüm.

Derleyip çalıştırmak için [`scripts/sitl.sh`](../scripts/sitl.sh), çalışan PX4'e dışarıdan komut göndermek için [`scripts/pxh.sh`](../scripts/pxh.sh) kullanıyorum.

Önceki: [1. PX4, Pixhawk ve ArduPilot](01-px4-pixhawk-ardupilot.md) · Sonraki: [3. Kurulum ve kullandığım komutlar](03-kurulum-ve-komutlar.md)
