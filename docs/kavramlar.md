# Kavramlar sözlüğü

PX4'ü okurken karşıma çıkan kavramları, STM32 ve FreeRTOS'tan bildiğim karşılıklarıyla eşleştirdim. Birebir aynı olmasalar da hangi rolü oynadıklarını anlamak için işime yaradı. Her kavramda bu çalışmada nerede gördüğümü de yazdım.

## Haberleşme: uORB

**uORB.** PX4'te modüllerin birbirine veri aktardığı publish/subscribe sistemi. Modüller birbirinin fonksiyonunu çağırmıyor; biri veriyi yayınlıyor, isteyen okuyor.
FreeRTOS karşılığı: Kuyruklar (queue) ve mailbox'lar. Farkı, bir kuyruğu genelde tek bir task okurken uORB'de aynı veriyi istediği kadar modül okuyabiliyor ve okuyanlar birbirini etkilemiyor.

**Topic.** uORB'de yayınlanan bir veri kanalı, örneğin `vehicle_attitude` ya da `sensor_gyro`. Her topic'in sabit bir veri yapısı var.
Gömülü karşılığı: Birden fazla task'ın okuduğu, korumalı bir global struct. Her okuyucunun "yeni veri geldi mi" bayrağı ayrı tutuluyor.
Bu çalışmada: `uorb top -1` ile tüm topic'leri listeledim (4. bölüm).

**Mesaj tanımı (.msg).** Topic'in içeriğini tanımlayan dosya, `msg/` klasöründe. Derleme sırasında her `.msg` dosyasından bir C struct'ı üretiliyor. Örneğin `msg/SensorGyro.msg` → `build/px4_sitl_default/uORB/topics/sensor_gyro.h` içinde `struct sensor_gyro_s`. SITL derlemesinde bu şekilde 237 topic başlığı üretiliyor.
Gömülü karşılığı: Task'lar arasında paylaşılan bir header dosyasındaki `typedef struct`. Farkı, elle değil otomatik üretilmesi.

**Publish (yayınlamak).** Bir modülün topic'e yeni veri yazması: `_pub.publish(veri)` ya da `orb_publish()`.
FreeRTOS karşılığı: `xQueueOverwrite()` ya da `xQueueSend()`.

**Subscribe ve update (abone olmak, okumak).** Bir modülün topic'i dinlemesi. `_sub.update(&veri)` yeni veri varsa kopyalayıp `true` döndürüyor, yoksa `false`.
FreeRTOS karşılığı: Sıfır bekleme süresiyle `xQueueReceive(q, &veri, 0)`.

**Kuyruk derinliği.** Bir topic'in kaç mesajı birikebildiği. Çoğu topic'te 1: okuyan sadece en son değeri görüyor. Ham sensör verisinde daha fazla, örneğin `sensor_gyro` için `ORB_QUEUE_LENGTH = 8`, çünkü örnek kaybolmamalı.
FreeRTOS karşılığı: `xQueueCreate(uzunluk, ...)` içindeki uzunluk. Derinlik 1 olunca `xQueueOverwrite()` ile kullanılan bir mailbox.

**Instance.** Aynı topic'in birden fazla kopyası. Örneğin 3 IMU varsa `sensor_gyro` 0, 1 ve 2 numaralı üç instance olarak yayınlanıyor; 5 MAVLink bağlantısı için `telemetry_status`'un 5 kopyası var.
Gömülü karşılığı: Aynı struct tipinden bir dizi; her sensöre bir eleman.

**listener.** `pxh>` konsolunda bir topic'in son mesajını ekrana basan komut. Debugger'da bir değişkeni "watch" penceresine eklemek gibi.

## Çalışma zamanı: modüller ve thread'ler

**Modül.** PX4'ün bir parçası: `ekf2`, `commander`, `mc_rate_control` gibi. Her biri `src/modules/` altında ayrı bir klasör; kendi başlatma, durdurma ve `status` komutları var.
Gömülü karşılığı: Projedeki bir uygulama bileşeni; init fonksiyonu ve task'ı olan bir `.c/.h` grubu.

**Task.** Kendi thread'i (kendi stack'i ve önceliği) olan modül. `commander`, `navigator`, `mavlink`, `logger` gibi.
FreeRTOS karşılığı: `xTaskCreate()` ile oluşturulan bir task.

**Work queue.** Birden fazla modülü sırayla çalıştıran ortak bir thread. Örneğin `wq:rate_ctrl` en yüksek öncelikli olan; açısal hız → rate kontrol → motor dağıtımı zinciri hep bu thread'de çalışıyor. Öncelik ve stack ayarları `WorkQueueManager.hpp` dosyasında.
FreeRTOS karşılığı: Bir task içinde, gelen olaya göre ilgili fonksiyonu çağıran bir olay döngüsü. FreeRTOS'un timer daemon task'ına da benziyor.

**Work item.** Kendi thread'i olmayan, bir work queue'ya kayıtlı modül. Sırası gelince `Run()` fonksiyonu çağrılıyor. Çoğu modül böyle: `ekf2`, kontrolcüler, sensör işleme.
FreeRTOS karşılığı: Timer callback'i ya da daemon task'a `xTimerPendFunctionCall()` ile gönderilen fonksiyon.

**Callback ile tetiklenme.** Modül, bir topic'e yeni veri gelince uyanıyor: `uORB::SubscriptionCallbackWorkItem`. Örneğin `mc_rate_control`, her `vehicle_angular_velocity` mesajında çalışıyor.
FreeRTOS karşılığı: ISR'den `xTaskNotifyGive()` ile task'ı uyandırmak.

**Periyodik çalışma.** Modül sabit aralıklarla çalışıyor: `ScheduleOnInterval()`. Örneğin `SensorGpsSim`, `ScheduleOnInterval(125_ms)` ile saniyede 8 kez.
FreeRTOS karşılığı: `vTaskDelayUntil()` ile periyodik task, ya da bir donanım timer kesmesi.

**NuttX.** PX4'ün gerçek kartlarda (Pixhawk) çalıştığı RTOS. POSIX uyumlu olduğu için aynı kod SITL'de Linux üzerinde de çalışabiliyor.
Karşılığı: FreeRTOS'un yerini tutan işletim sistemi. Daha büyük, dosya sistemi ve kabuğu (`nsh>`) olan bir RTOS.

**hrt_abstime.** PX4'ün zaman tipi: açılıştan beri geçen süre, mikrosaniye, `uint64_t`. Bütün mesajların `timestamp` alanı bu tipte. 5. bölümdeki taşma hatası bununla ilgiliydi.
Gömülü karşılığı: Mikrosaniye sayan, taşmaması için 64 bite genişletilmiş bir timer sayacı. `HAL_GetTick()`'in daha hassası.

**Lockstep.** SITL'de PX4 ile simülatörün aynı sanal saate göre adım adım ilerlemesi. Bilgisayar yavaşlasa da kontrol döngülerinin zamanlaması bozulmuyor.
Gömülü karşılığı: Debugger'da iki sistemi aynı anda tek adım ilerletmek gibi; zaman gerçek saatle değil adım sayısıyla akıyor.

## Yapılandırma

**Parametre.** Kodu yeniden derlemeden değiştirilebilen ayar. Örneğin `MC_ROLLRATE_P` (roll hız kontrolcüsünün P kazancı, varsayılan 0.15) ya da `SDLOG_MODE`. Kodda `PARAM_DEFINE_FLOAT(...)` ile tanımlanıyor, `param set` ile değiştiriliyor. SITL'de `parameters.bson` dosyasına kaydediliyor, gerçek kartta kalıcı belleğe.
Gömülü karşılığı: EEPROM'a ya da flash'ın bir sayfasına kaydedilen bir ayar struct'ı.

**Board.** Belirli bir donanımın tanımı: `boards/px4/fmu-v6x/` gibi. Pin atamaları, hangi sensörün hangi bus'ta olduğu ve hangi modüllerin derleneceği burada.
Gömülü karşılığı: CubeMX'teki `.ioc` dosyası ve BSP.

**.px4board.** Bir derlemeye hangi modüllerin gireceğini seçen dosya: `CONFIG_MODULES_MC_RATE_CONTROL=y` gibi satırlardan oluşuyor. `boards/px4/sitl/default.px4board` benim derlediğim yapılandırma.
Gömülü karşılığı: CubeMX'te middleware'leri seçmek, ya da `FreeRTOSConfig.h`'deki `#define` ayarları.

**Başlangıç betiği (rcS).** PX4 açılırken hangi modüllerin hangi sırayla başlatılacağını belirleyen betik. SITL'de `ROMFS/px4fmu_common/init.d-posix/rcS`. `SDLOG_MODE`'un varsayılanının 1 olduğunu da burada buldum.
Gömülü karşılığı: `main()` içindeki `MX_..._Init()` çağrıları ve `xTaskCreate()` sırası.

**Airframe (SYS_AUTOSTART).** Araç tipine göre hazır ayar seti. Bende `SYS_AUTOSTART=10040`, yani `10040_sihsim_quadx`: SIH'te quadcopter. Aynı yazılım farklı airframe ile sabit kanat ya da rover olabiliyor.
Gömülü karşılığı: Aynı firmware'in farklı ürün varyantları için seçilen yapılandırma.

## Uçuş tarafı

**Arm / disarm.** Motorların çalışmasına izin verilmesi ya da kesilmesi. Disarm'dayken kontrolcüler hesap yapsa bile motorlar dönmüyor.
Gömülü karşılığı: PWM çıkışlarını aktif eden bir emniyet kilidi, ya da motor sürücüsünün enable pini.

**Uçuş modu (nav_state).** Aracın o anki davranışı: Takeoff, Hold, Position, Descend, Land. `vehicle_status.nav_state` alanında bir sayı olarak tutuluyor; ben 4 (Hold) ve 12 (Descend) değerlerini gördüm.
Gömülü karşılığı: Ana durum makinesinin (state machine) o anki durumu.

**Setpoint.** Bir kontrolcüye verilen hedef değer: "şu yükseklikte dur", "şu açıda eğil".
Gömülü karşılığı: PID döngüsünün referans (hedef) değeri.

**Kaskad kontrol.** İç içe PID döngüleri: konum → duruş (attitude) → açısal hız (rate). Dıştaki döngünün çıkışı içtekinin setpoint'i oluyor; içteki daha hızlı çalışıyor.
Gömülü karşılığı: Motor kontrolünde akım döngüsünün içinde, onun dışında hız, en dışta konum döngüsü olması.

**Control allocator.** İstenen tork ve itkiyi motorlara paylaştıran modül. Eski PX4 sürümlerinde "mixer" deniyordu.
Gömülü karşılığı: Motor karıştırma matrisi. Her motora ne kadar komut gideceğini hesaplayan bir matris çarpımı.

**EKF2 (durum tahmincisi).** IMU, GPS, barometre ve manyetometreyi birleştirip aracın konumunu, hızını ve duruşunu tahmin eden genişletilmiş Kalman filtresi.
Gömülü karşılığı: IMU füzyonu için kullanılan complementary filtre ya da Madgwick filtresinin çok daha kapsamlı hali.

**Failsafe.** Bir şey ters gidince (GPS kaybı, düşük batarya, bağlantı kopması) aracı güvenli bir duruma geçiren mekanizma. 5. bölümde GPS kesilince aracı kendiliğinden indirdi.
Gömülü karşılığı: Watchdog ya da hata durumunda sistemi güvenli moda alan handler.

**NED ve FRD.** PX4'ün eksen tanımları. NED dünyaya göre: kuzey, doğu, aşağı. FRD araca göre: ileri, sağ, aşağı. İkisinde de Z aşağıyı gösterdiği için yükseklik ve ivmeölçerin yerdeki değeri eksi çıkıyor.

## Dış dünya

**MAVLink.** Araç ile yer istasyonu (QGroundControl) arasındaki haberleşme protokolü. Her mesajın bir ID'si, sabit bir yapısı ve CRC'si var.
Gömülü karşılığı: UART üzerinden kendi tanımladığın, başlıklı ve CRC'li bir paket protokolü. CAN mesajlarına da benziyor.

**vehicle_command ve vehicle_command_ack.** PX4 içinde bir modülden diğerine "şunu yap" demek ve cevabını almak için kullanılan iki topic. QGC'den gelen komutlar da `mavlink` modülü tarafından `vehicle_command`'a çevriliyor.
Gömülü karşılığı: Bir istek mesajı gönderip ACK beklemek, gelmezse timeout'a düşmek. `failure gps off`'un timeout vermesi tam olarak buydu.

**ULog (.ulg).** PX4'ün uçuş log formatı. `logger` modülü topic'leri ikili (binary) olarak dosyaya yazıyor; ben `pyulog` ile okudum.
Gömülü karşılığı: SD karta binary log tutmak.

**pxh> ve nsh>.** PX4'ün komut satırı. SITL'de `pxh>`, gerçek kartta NuttX'in `nsh>` kabuğu (USB ya da UART üzerinden).
Gömülü karşılığı: UART üzerinden komut alan bir CLI ya da debug konsolu.

Okuma sırasına dön: [README](../README.md)
