# 1. PX4, Pixhawk ve ArduPilot

## Uçuş kontrolcüsü

Bir drone'un beyni uçuş kontrolcüsüdür (flight controller). Sensörlerden (IMU, barometre, manyetometre, GPS) veri okur, aracın konumunu ve duruşunu tahmin eder, sonra motorlara ne kadar güç verileceğini hesaplar. Bunu saniyede yüzlerce kez yapar.

Donanım tarafı bir kart, yazılım tarafı da o kartta çalışan firmware. Bu ikisini ayrı düşünmek gerekiyor, çünkü aynı karta farklı firmware'ler yüklenebiliyor.

## Pixhawk (donanım)

Pixhawk açık bir donanım standardı. Tek bir ürün değil: Holybro, CUAV, CubePilot gibi firmalar bu standarda uyan kartlar üretiyor. Kartların içinde bir STM32 mikrodenetleyici, birkaç IMU, barometre, manyetometre ve GPS, telemetri, motor çıkışları için portlar var.

PX4 kaynak kodunda bu kartlar `boards/px4/` altında `fmu-v2`, `fmu-v5`, `fmu-v6x` gibi isimlerle duruyor. Örneğin Pixhawk 6X'in (fmu-v6x) işlemcisi STM32H753. Yani STM32 tarafında bildiğim şeyler burada da geçerli; sadece üstünde çok daha büyük bir yazılım çalışıyor.

## PX4 (yazılım)

PX4 açık kaynak bir uçuş yazılımı. ETH Zürih'te başladı, şu an Linux Foundation altındaki Dronecode tarafından yönetiliyor. BSD lisanslı olduğu için ticari ürünlerde de rahat kullanılıyor.

Benim için önemli olan özellikleri:

- Gerçek donanımda **NuttX** RTOS üzerinde çalışıyor (FreeRTOS yerine).
- Modüller birbirini doğrudan çağırmıyor, **uORB** denen bir publish/subscribe sistemiyle haberleşiyor. Bir modül veriyi bir "topic"e yayınlıyor, ihtiyacı olan diğer modüller abone oluyor.
- Multikopter, sabit kanat, VTOL, rover gibi farklı araç tipleri aynı kod tabanında.

## ArduPilot (diğer büyük alternatif)

ArduPilot da açık kaynak bir uçuş yazılımı ve PX4'ten daha eski (Arduino tabanlı ArduPilotMega kartından çıktı). Pixhawk kartlarında o da çalışıyor; kart aynı kalıyor, sadece yüklenen firmware değişiyor.

| | PX4 | ArduPilot |
|---|---|---|
| Lisans | BSD | GPLv3 |
| RTOS (STM32 kartlarda) | NuttX | ChibiOS |
| Modüller arası haberleşme | uORB (publish/subscribe) | Ortak sınıflar, HAL üzerinden doğrudan çağrılar |
| Durum tahmini | EKF2 | EKF3 (AP_NavEKF3) |
| Genelde kullanılan yer istasyonu | QGroundControl | Mission Planner |

Kabaca: ArduPilot hobi ve saha kullanımında çok yaygın ve çok olgun. PX4 ise modüler yapısı ve lisansı yüzünden şirketlerin ve araştırma gruplarının tercihi olabiliyor. İkisi de MAVLink protokolünü konuştuğu için yer istasyonları ve araçlar birbiriyle uyumlu.

Ben PX4'ü seçtim. Sebebi uORB ve modül yapısının, FreeRTOS'ta task'lar ve kuyruklarla kurduğum yapılara benzemesi; kodu okurken nereye bakacağımı daha kolay anlıyorum.

Sonraki: [2. SITL, simülatörler ve QGroundControl](02-sitl-ve-simulatorler.md)
