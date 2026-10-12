# PX4 SITL çalışmalarım

STM32 ve FreeRTOS üzerinde gömülü yazılım geliştiriyorum. Bu repoda drone uçuş yazılımı PX4'ü öğrenirken yaptıklarımı tutuyorum. Elimde donanım olmadığı için her şeyi simülasyonda (SITL) yaptım: PX4'ü kaynaktan derledim, QGroundControl ile uçurdum, uçuş loglarını analiz ettim.

## Okuma sırası

1. [PX4, Pixhawk ve ArduPilot](docs/01-px4-pixhawk-ardupilot.md): Uçuş kontrolcüsü nedir, donanım ve yazılım tarafı, iki büyük açık kaynak proje
2. [SITL, simülatörler ve QGroundControl](docs/02-sitl-ve-simulatorler.md): Donanım olmadan nasıl çalıştım, hangi araçları kullandım
3. [Kurulum ve kullandığım komutlar](docs/03-kurulum-ve-komutlar.md): Hangi komutu nerede ve neden çalıştırdım, adım adım
4. [PX4 mimarisi: uORB ve modüller](docs/04-mimari-uorb.md): Modül şeması, thread'ler, topic'ler, ilk kod değişikliğim
5. [Kontrol döngüleri ve GPS kaybı](docs/05-kontrol-ve-gps-kaybi.md): Havada kontrol zinciri, GPS kesilince ne oluyor, log analizi

Okurken yanında açık tutmak için: [Kavramlar sözlüğü](docs/kavramlar.md). uORB, topic, work queue, parametre gibi PX4 kavramları ve STM32/FreeRTOS'taki karşılıkları.

![GPS kaybı](analysis/plots/gps_loss_overview.png)

## Klasörler

```
docs/       notlar (yukarıdaki sırayla) ve kavramlar sözlüğü
scripts/    sitl.sh: derle ve çalıştır, pxh.sh: çalışan PX4'e komut gönder
analysis/   uçuş logu analiz scripti ve grafikler
```

PX4 üzerindeki kod değişikliklerim fork'umda: [batuuhnk/PX4-Autopilot](https://github.com/batuuhnk/PX4-Autopilot/tree/learning/sitl-week1)

## Çalıştırma

```bash
git clone --recursive --depth 1 --branch v1.17.0 https://github.com/PX4/PX4-Autopilot.git ~/px4/PX4-Autopilot
./scripts/sitl.sh                            # derle ve SIH ile başlat
./scripts/pxh.sh listener vehicle_attitude   # bir topic'i oku
```

Ayrıntılı kurulum adımları 3. bölümde. Log analizi (pyulog ve matplotlib gerekiyor, PX4'ün Docker imajında ikisi de var):

```bash
python3 analysis/gps_loss.py <ucus_logu.ulg> analysis/plots
```

## Sırada

- SIH simülatörüne GPS hata enjeksiyonu eklemek (şu an çalışmıyor, bkz. 5. bölüm)
- ArduPilot mimarisiyle daha ayrıntılı karşılaştırma
