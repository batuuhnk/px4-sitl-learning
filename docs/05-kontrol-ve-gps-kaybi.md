# 5. Kontrol döngüleri ve GPS kaybı

## Aracı nasıl uçurdum?

Drone'u elle (kumanda ya da joystick ile) uçurmadım. PX4'ün otomatik kalkış modunu kullandım; araç kendi kendine kalkıp havada bekledi. QGroundControl'ü bu sırada sadece izlemek için açık tuttum: haritada konumu, yüksekliği ve uçuş modunu oradan takip ettim.

### Kalkış komutu

PX4 ayrı bir terminalde `~/px4/sitl.sh` ile çalışırken, **Ubuntu terminalinden** şu komutu gönderdim:

```bash
~/px4/pxh.sh commander takeoff
```

Bu, PX4 konsoluna `commander takeoff` yazmakla aynı şey. Sonrasında olanlar:

1. `commander` aracı arm etti (motorlar çalıştı) ve uçuş modunu **Takeoff**'a aldı.
2. Araç `MIS_TAKEOFF_ALT` parametresindeki yüksekliğe (varsayılan 2.5 m) dikey olarak tırmandı.
3. Hedef yüksekliğe ulaşınca mod kendiliğinden **Hold**'a geçti. Araç olduğu yerde asılı kaldı (hover).

Yüksekliği birkaç saniyede bir okuyarak tırmanışı da takip ettim:

```bash
~/px4/pxh.sh listener vehicle_local_position
```

`z` değeri 0'dan -2.2'ye indi. PX4 dünya ekseninde NED (kuzey, doğu, aşağı) kullandığı için yukarı çıkmak z'nin eksi yönde büyümesi demek.

### QGroundControl'den de yapılabilirdi

QGC'deki **Takeoff** düğmesi aynı işi yapıyor. Fark sadece komutun geldiği yol:

```
QGC "Takeoff" düğmesi  -> MAVLink mesajı (UDP 14550) -> mavlink modülü -> vehicle_command -> commander
pxh> commander takeoff ->                                                   vehicle_command -> commander
```

İki durumda da `commander` aynı `vehicle_command` mesajını alıyor (4. bölümdeki "Karar ve haberleşme" şeması). Ben terminali tercih ettim, çünkü komutları ve ölçümleri aynı yerden, tekrarlanabilir şekilde çalıştırabiliyordum.

### Uçuştaki diğer komutlar

Araç havadayken sırasıyla şunları çalıştırdım (hepsi Ubuntu terminalinden, `pxh.sh` ile):

```bash
~/px4/pxh.sh param set SYS_FAILURE_EN 1    # hata enjeksiyonunu aç
~/px4/pxh.sh failure gps off               # GPS hatası dene (SIH'te çalışmadı, aşağıda)
~/px4/pxh.sh sensor_gps_sim stop           # GPS'i gerçekten kes
~/px4/pxh.sh sensor_gps_sim start          # iniş bittikten sonra GPS'i geri aç
```

İnişi ben komut vererek yapmadım. GPS kesilince PX4'ün failsafe mekanizması aracı kendisi indirdi ve motorları kapattı. Bu da deneyin asıl gözlemlerinden biri oldu.

## Havada kontrol zinciri

Araç yaklaşık 2.2 m'de havada sabit dururken (hover) her kontrol katmanının girişini ve çıkışını okudum:

| Katman | Hedef | Ölçülen |
|---|---|---|
| Konum | z = -2.246 m | z = -2.234 m |
| Attitude | roll 0.5°, pitch -0.2° | roll 0.3°, pitch -0.6° |
| Rate | roll -0.05 rad/s | roll 0.16 rad/s |
| Tork | x = +0.039 | |
| Motorlar | 0.451, 0.519, 0.496, 0.461 | |

Motorların ortalaması 0.48, yani araç havada kalmak için motorlarının yaklaşık yarısını kullanıyor. Sol motorlar (M2, M3) sağdakilerden biraz fazla dönüyor; bu da tork satırındaki pozitif roll değeriyle (aracı sağa yatırma) uyumlu.

Bu değerleri sırayla okuduğum için aralarında birkaç yüz milisaniye fark var. Kesin karşılaştırma için uçuş logunu kullandım:

![Hover sırasında roll ekseni](../analysis/plots/hover_cascade.png)

Üstteki grafikte konum kontrolcüsünün istediği açı ±1.5° arasında sıçrıyor, gerçek açı ise yumuşak ilerliyor. Alttaki grafikte gyro ölçümü çok gürültülü, rate kontrolcüsü gürültüyü değil genel eğilimi takip ediyor.

## GPS kaybı deneyi

Araç havadayken GPS'i kesip EKF2'nin (durum tahmincisi) ve failsafe mekanizmasının ne yaptığına baktım.

### `failure gps off` çalışmadı

PX4'te hata simülasyonu için `failure` komutu var, ama SIH'te GPS için çalışmadı ("Timeout waiting for ack"). Kaynak kodda sebebini buldum: GPS hata enjeksiyonu sadece `simulator_mavlink` modülünde yazılmış (Gazebo ve jMAVSim bunu kullanıyor). SIH'in GPS'ini üreten `sensor_gps_sim` bu komutu işlemiyor, `commander` da "başka modül halleder" diye pas geçiyor. Komutu kimse cevaplamadığı için zaman aşımı oluyor.

Bunun yerine GPS modülünü uçuş sırasında durdurdum (`sensor_gps_sim stop`). Gerçek araçta GPS kablosunun kopması gibi.

### Sonuç

![GPS kaybı](../analysis/plots/gps_loss_overview.png)

Logdan çıkan zaman çizelgesi:

```
1643.9 s  son GPS mesajı
1650.0 s  commander failsafe: Descend (kör iniş)     +6.1 s
1651.8 s  EKF2 GPS füzyonunu bıraktı                 +7.9 s
~1654.3 s araç yere indi
1657.1 s  disarm
```

Gözlemlerim:

1. **Araç, tahmin değişmeden önce kaydı.** GPS kesildikten sonraki ilk 4 saniyede araç gerçekte yaklaşık 6 m kaydı, EKF2'nin tahmini ise yerinde kaldı. Kontrolcü sadece tahminin gösterdiği konumu bildiği için bu kaymayı düzeltemedi.
2. **Sadece IMU ile konum tahmini çok çabuk bozuluyor.** Sonra tahmin ters yöne kaçmaya başladı ve hata 15 saniyede 35 m'ye çıktı. İvmeölçerdeki küçük bir sapma iki kez integre edildiği için hata zamanın karesiyle büyüyor.
3. **Failsafe, EKF2 GPS'i bırakmadan önce devreye girdi.** Commander konum doğruluğu belli bir eşiği geçince (`COM_POS_FS_EPH`) karar veriyor, EKF2'nin bayrağını beklemiyor.
4. İrtifa barometre sayesinde korundu, ama yere inerken tahmin 0.4 m yerin altını gösterdi.
5. GPS'i geri açınca EKF2 konumu hemen düzeltti.

## Log analizi

Grafikleri [`analysis/gps_loss.py`](../analysis/gps_loss.py) ile çizdim. Script, `.ulg` uçuş logunu `pyulog` ile okuyup olay anlarını buluyor ve iki grafiği üretiyor.

Yazarken iki hata yaptım:

- Zaman damgaları `uint64`. Log başlangıcından önceki bir değerden çıkarma yapınca sayı taşıyıp çok büyük değerler verdi. Mikrodenetleyicide `uint32_t` tick sayacıyla yaşanan taşma ile aynı hata. Önce float'a çevirerek çözdüm.
- GPS kesintisini GPS mesajları arasındaki boşluktan bulmaya çalıştım, ama logger disarm'da kapandığı için GPS'in geri geldiği an logda yoktu. EKF2'nin `cs_gnss_pos` bayrağına bakarak çözdüm.

Önceki: [4. PX4 mimarisi](04-mimari-uorb.md)
