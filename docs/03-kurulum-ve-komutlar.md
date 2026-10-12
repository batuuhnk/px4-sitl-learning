# 3. Kurulum ve kullandığım komutlar

Linux tecrübem az olduğu için yaptığım her adımı, hangi komutu nerede çalıştırdığımı ve ne işe yaradığını buraya yazdım. Başka biri de bu sırayla aynı ortamı kurabilir.

## Önce: nerede çalıştırıyorum?

Bu çalışmada dört farklı yerde komut yazdım. Hangisinde olduğunu her adımın başında belirttim.

| Yer | Nasıl açılıyor | Satır başında görünen |
|---|---|---|
| **Ubuntu terminali** | Ctrl+Alt+T | `batu@batu-VirtualBox:~$` |
| **PX4 konsolu** | PX4 çalışınca aynı terminalde açılıyor | `pxh>` |
| **VS Code** | Kod düzenleme için | |
| **VirtualBox / tarayıcı** | Windows tarafında, ya da Ubuntu'daki Firefox | |

İşime yarayan birkaç temel şey:

```bash
pwd                 # şu an hangi klasördeyim
ls                  # klasörde ne var
cd ~/px4            # klasöre git (~ = ev klasörüm, /home/batu)
df -h /             # diskte ne kadar yer var
sudo <komut>        # komutu yönetici olarak çalıştır, şifre ister
```

- `sudo` şifreyi sorarken ekranda hiçbir şey görünmez, bu normal. Birkaç dakika içinde yazılmazsa zaman aşımına uğruyor.
- Ctrl+C çalışan komutu durdurur. Yukarı ok tuşu önceki komutu geri getirir. Tab tuşu dosya ve komut adlarını tamamlar.

## Adım 1: apt'nin internete çıkması

**Ubuntu terminali.** `sudo apt update` 403 Forbidden hatası verdi. Bağlantım düz HTTP isteklerini engelliyordu, HTTPS'te sorun yoktu. Paket kaynaklarını HTTPS'e çevirerek çözdüm:

```bash
sudo sed -i 's|http://|https://|g' /etc/apt/sources.list.d/ubuntu.sources
sudo apt update
```

`sed -i` dosyanın içinde bul-değiştir yapıyor. Burada `http://` geçen her yeri `https://` yaptı.

## Adım 2: Docker

**Ubuntu terminali.** PX4'ü container içinde derleyip çalıştıracağım için Docker'ı kurdum:

```bash
sudo apt install docker.io
sudo usermod -aG docker $USER     # kullanıcımı docker grubuna ekle
```

İkinci komut, her seferinde `sudo docker ...` yazmamak için. Grup değişikliğinin geçerli olması için oturumu kapatıp açmak gerekiyor. Ben bunu sonradan fark ettim, o zamana kadar `sudo` ile çalıştım.

```bash
docker ps          # çalışan container'ları listeler; hata vermiyorsa kurulum tamam
```

## Adım 3: Hazır PX4 imajıyla ilk deneme

**Ubuntu terminali.** Kaynaktan derlemeden önce PX4'ün hazır imajıyla denedim:

```bash
docker run --rm -it --network host px4io/px4-sitl:latest
```

- `--rm`: kapanınca container'ı sil
- `-it`: terminale bağlan, PX4 konsoluna yazabileyim
- `--network host`: container host ile aynı ağı kullansın. İlk denemede bunun yerine `-p 14550:14550/udp` kullanmıştım ve QGroundControl bağlanamadı.

Açılınca terminal `pxh>` konsoluna dönüyor ve "Ready for takeoff!" yazıyor.

## Adım 4: QGroundControl

**Tarayıcı + Ubuntu terminali.** QGroundControl'ün GitHub sayfasından `QGroundControl-x86_64.AppImage` dosyasını indirdim. AppImage kurulum gerektirmeyen, tek dosyalık bir program:

```bash
chmod +x QGroundControl-x86_64.AppImage    # dosyaya çalıştırma izni ver
./QGroundControl-x86_64.AppImage           # çalıştır
```

PX4 çalışıyorsa QGC birkaç saniye içinde kendiliğinden bağlanıyor.

## Adım 5: Diski büyütmek

PX4'ün kaynak kodu, derleme çıktısı ve Docker imajı birlikte ~15 GB tutuyor. Sanal diskimde 3 GB boş yer kalmıştı.

**VirtualBox (Windows tarafında), VM kapalıyken:** File → Tools → Media → sanal diski seç → Size'ı 40 GB yap → Apply.

**Ubuntu terminali, VM açıldıktan sonra:** VirtualBox diski büyüttü ama Ubuntu'daki bölüm hâlâ eski boyuttaydı:

```bash
lsblk                         # diskler ve bölümler: sda 40G, sda2 hâlâ 20G
sudo growpart /dev/sda 2      # 2. bölümü diskin sonuna kadar uzat
sudo resize2fs /dev/sda2      # dosya sistemini yeni boyuta genişlet
df -h /                       # kontrol: 40G
```

## Adım 6: PX4 kaynak kodunu indirmek

**Ubuntu terminali:**

```bash
mkdir -p ~/px4 && cd ~/px4
git clone --recursive --depth 1 --shallow-submodules --branch v1.17.0 \
    https://github.com/PX4/PX4-Autopilot.git
```

- `--branch v1.17.0`: son kararlı sürüm
- `--depth 1`: tüm geçmişi değil sadece bu sürümü indir, çok daha küçük
- `--recursive`: PX4'ün içindeki alt projeleri de indir (NuttX, MAVLink vb.)

## Adım 7: Derleme ortamı

PX4'ün kurulum betiği (`Tools/setup/ubuntu.sh`) sadece Ubuntu 22.04 ve 24.04'ü destekliyor, bende 26.04 var. Bu yüzden derleyiciyi kendi bilgisayarıma kurmak yerine PX4'ün resmi derleme imajını kullandım.

**Ubuntu terminali:**

```bash
docker pull px4io/px4-dev:v1.16.0-rc1-258-g0369abd556
```

Bu imajın adını PX4 kaynağındaki `Tools/docker_run.sh` dosyasından aldım.

## Adım 8: Derlemek ve çalıştırmak

**Ubuntu terminali.** Kod bilgisayarımda duruyor, container'a bağlanıyor (`-v`), derleme container'ın içinde oluyor:

```bash
docker run -it --rm --network host --name px4dev \
    --user $(id -u):$(id -g) -e HOME=/tmp \
    -v ~/px4/PX4-Autopilot:/home/batu/px4/PX4-Autopilot \
    -w /home/batu/px4/PX4-Autopilot \
    px4io/px4-dev:v1.16.0-rc1-258-g0369abd556 \
    bash -c "make px4_sitl sihsim_quadx j=2"
```

- `make px4_sitl`: SITL için derle (CubeIDE'deki Build)
- `sihsim_quadx`: derledikten sonra SIH simülatörü ve quadcopter modeliyle çalıştır (Run)
- `j=2`: aynı anda 2 dosya derle. Sanal makinemde 4 GB RAM var, fazlası belleği taşırıyor.
- `--user`: oluşan dosyalar root'a değil bana ait olsun

İlk derleme 1109 adım ve yaklaşık 30 dakika sürdü. Sonrakiler sadece değişen dosyaları derlediği için birkaç dakika.

Bu uzun komutu her seferinde yazmamak için [`scripts/sitl.sh`](../scripts/sitl.sh) betiğine koydum:

```bash
chmod +x ~/px4/sitl.sh      # bir kere, çalıştırma izni
~/px4/sitl.sh               # derle + çalıştır
~/px4/sitl.sh build         # sadece derle
```

## Adım 9: PX4 konsolunda kullandığım komutlar

**PX4 konsolu (`pxh>`).** Önemli bir not: bu konsola komut yapıştırınca "Invalid command" hatası alıyordum. Terminal yapıştırılan metnin başına görünmez karakterler ekliyor, `pxh>` bunları tanımıyor. Komutları elle yazmak gerekiyor.

```
help                                  tüm komutların listesi
uorb top -1                           topic'lerin yayın hızları ve abone sayıları
listener vehicle_attitude             bir topic'in son mesajını göster
work_queue status                     hangi modül hangi thread'de çalışıyor
param set SDLOG_MODE 0                logu sadece arm ile disarm arasında tut
logger stop                           log kaydını durdur
commander takeoff                     kalkış
px4_simple_app                        kendi değiştirdiğim örnek modül
param set SYS_FAILURE_EN 1            hata enjeksiyonunu aç
failure gps off                       GPS hatası (SIH'te çalışmıyor, 5. bölüm)
sensor_gps_sim stop                   GPS simülatörünü durdur (GPS kaybı)
sensor_gps_sim start                  GPS'i geri aç
shutdown                              PX4'ü kapat
```

`SDLOG_MODE` ayarını değiştirmemin sebebi: varsayılan ayarda log açılışta başlıyor ve araç hiç uçmasa bile büyümeye devam ediyor. Bir seferinde 1 GB'lık dosyalar oluşup diski dolduruyordu.

Konsola elle yazmak yerine normal terminalden komut gönderebilmek için [`scripts/pxh.sh`](../scripts/pxh.sh) yazdım. **Ubuntu terminalinde**, PX4 başka bir terminalde çalışırken:

```bash
~/px4/pxh.sh listener vehicle_attitude
~/px4/pxh.sh commander takeoff
```

Arka planda `docker exec` ile çalışan container'ın içinde komutu çalıştırıyor.

## Adım 10: VS Code

**Ubuntu terminali:**

```bash
sudo snap install code --classic
code ~/px4/PX4-Autopilot           # projeyi VS Code'da aç
```

**VS Code:** Ctrl+Shift+X → "C/C++" (Microsoft) eklentisini kurdum. Ctrl+tık ile fonksiyonun tanımına gidebilmek için `.vscode/c_cpp_properties.json` dosyasında eklentiyi derlemenin ürettiği `build/px4_sitl_default/compile_commands.json` dosyasına yönlendirdim.

Kod değiştirme döngüm: VS Code'da düzenle, Ctrl+S → terminalde `~/px4/sitl.sh` → `pxh>` konsolunda dene.

## Adım 11: Git ve GitHub

**Ubuntu terminali, PX4 klasöründe** (`cd ~/px4/PX4-Autopilot`):

```bash
git config user.name "Batuhan Kilicli"
git config user.email "..."
git switch -c learning/sitl-week1        # kendi değişikliklerim için yeni dal
git add src/examples/px4_simple_app/px4_simple_app.c
git commit                                # değişikliği kaydet
```

**Tarayıcı:** github.com/PX4/PX4-Autopilot sayfasında Fork'a bastım, kendi hesabımda bir kopyası oluştu.

**Ubuntu terminali:**

```bash
sudo apt install gh                       # GitHub komut satırı aracı
gh auth login --web                       # tarayıcıdan GitHub hesabımla giriş
git remote add fork https://github.com/batuuhnk/PX4-Autopilot.git
git push -u fork learning/sitl-week1      # dalı kendi fork'uma gönder
```

`origin` PX4'ün resmi reposu (sadece okuyorum), `fork` benim kopyam (değişikliklerimi buraya gönderiyorum).

## Adım 12: Log analizi

Uçuş logları PX4 klasöründe `build/px4_sitl_default/rootfs/log/` altında `.ulg` uzantılı dosyalar olarak duruyor. Analiz için gereken Python kütüphaneleri (pyulog, matplotlib) PX4'ün derleme imajında zaten var.

**Ubuntu terminali:**

```bash
docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp \
    -v ~/px4:/home/batu/px4 -w /home/batu/px4/analysis \
    px4io/px4-dev:v1.16.0-rc1-258-g0369abd556 \
    python3 gps_loss.py <log_dosyasi.ulg> .
```

Önceki: [2. SITL ve simülatörler](02-sitl-ve-simulatorler.md) · Sonraki: [4. PX4 mimarisi: uORB ve modüller](04-mimari-uorb.md)
