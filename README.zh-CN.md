# SM-T733 / gts7fewifi TWRP 解密实验版编译说明

版本：T733-LOS23.2-CRYPTO-V2，2026-10-28。

本包来自此次成功编译的实际设备树，不是原仓库 main 分支的旧版本。包含设备配置、DYE1 预编译 kernel/DTB/Recovery DTBO、七个触摸模块和固件、指定 LineageOS 的四份硬件密钥相关库，以及匹配现有 TWRP 的基础库以及构建工具。无需依赖原作者电脑上的路径或另外提取这些文件。

## 已验证与未验证

- 此配置曾在 Ubuntu 22.04 / TWRP android-12.1 完成编译；本次产物 Header v2、board SRPUF17A009、屏幕配置 1600×2560、Recovery 容量 81,788,928 字节（78 MiB）。
- 主程序完整加密支持、ramdisk 库哈希、触摸晚加载、镜像结构、AVB 签名和 LZ4/TAR 内容检查通过。
- 先前基线版本的启动、显示和触摸实机通过；V2 参考包启动和 Data 解密已由用户确认，其他功能仍按已明确的范围记录。
- **用户已在指定 LineageOS 23.2 上确认 V2 成功启动并解密 Data。**此结论来自用户实机反馈，不扩大为所有 ROM、口令或功能通过；新编译镜像仍需回归测试。

## 适用范围及来源

设备：SM-T733 Wi-Fi，gts7fewifi；不适用于 T736B 等其他型号。

kernel、DTB、Recovery DTBO、触摸模块来自匹配的 T733ZCS9DYE1 固件，kernel 5.4.254-qgki-1570070-abT733ZCS9DYE1。密钥相关库来自 lineage-23.2-20260223-UNOFFICIAL-gts7fewifi（SDK 36，安全补丁 2026-02-01）：

https://github.com/Bush-cat/android_device_samsung_gts7fewifi/releases/tag/los23.2-testing

设备树来源：https://github.com/chingmiles/android_device_samsung_gts7fewifi 。本次 GitHub 更新包含已实测 V2 配置；首次获取请使用当前提交。保留原文件版权声明；固件和 vendor 预编译二进制的权利归原权利人，本包不将其重新声明为开源代码。

## 1. 编译环境

建议 Ubuntu 22.04 x86_64 或 WSL2 Ubuntu 22.04。源码存放在 Linux 文件系统，例如 ~/android/twrp，不要放在 /mnt/c、/mnt/h 等 Windows 挂载盘。建议内存 16 GiB 以上，32 GiB 更稳妥；首次同步和编译建议预留 150–200 GiB，视同步方式和已有缓存而变化。

安装常见依赖（Ubuntu 22.04）：

```bash
sudo apt update
sudo apt install git git-lfs curl ca-certificates build-essential bc bison flex gcc-multilib g++-multilib zip unzip rsync cpio lz4 python3 python-is-python3 libssl-dev libelf-dev libncurses5 libncurses5-dev lib32z1-dev libxml2-utils xsltproc fontconfig
mkdir -p ~/bin
curl -fL https://storage.googleapis.com/git-repo-downloads/repo -o ~/bin/repo
chmod +x ~/bin/repo
export PATH="$HOME/bin:$PATH"
```

Android 编译所用 JDK/Clang/Python 组件以同步的源码预编译工具为准，不必强制改用宿主机的旧 Java。

## 2. 同步 TWRP 源码

```bash
mkdir -p ~/android/twrp
cd ~/android/twrp
repo init --depth=1 -u https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp.git -b twrp-12.1
repo sync -j4
```

本机成功构建使用 minimal-manifest-twrp 的 twrp-12.1，核心 Recovery 为 TeamWin android-12.1。不要因为 ROM 是 Android 16 就把同一设备树直接移到其他构建分支。

同步和分支说明的上游来源：https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp/tree/twrp-12.1

## 3. 放置设备树及公共依赖

在 TWRP 源码根目录获取本设备树（已有目录请先备份）：

```bash
git clone https://github.com/chingmiles/android_device_samsung_gts7fewifi.git device/samsung/gts7fewifi
```

也可以将源码包的 gts7fewifi 整个目录放入 device/samsung/：

```text
<TWRP源码>/device/samsung/gts7fewifi/BoardConfig.mk
<TWRP源码>/device/samsung/gts7fewifi/recovery/
<TWRP源码>/device/samsung/gts7fewifi/prebuilt/
```

请在新目录安装，已有设备树应先备份。公共依赖在 twrp.dependencies 中列出；若同步结果尚未包含它，可在源码根目录执行：

```bash
if [ ! -d device/qcom/twrp-common ]; then
  git clone --branch android-12.1 https://github.com/TeamWin/android_device_qcom_twrp-common.git device/qcom/twrp-common
fi
```

在设备树目录可先检查下载内容（解压 ZIP 时保留文件名和 LF 换行，禁止将预编译二进制当成 Git LFS 指针文本）：

```bash
python3 tools/check_source_assets.py
```

## 4. 编译、验包及打包

在 TWRP 源码根目录执行：

```bash
T733_JOBS=4 bash device/samsung/gts7fewifi/tools/build_portable.sh
```

脚本调用 lunch twrp_gts7fewifi-eng 和 recoveryimage，检查 module/mkbootimg 实现，完成 Header/DTB/DTBO/模块/AVB 核查，再检查解密编译与预编译库哈希，生成 LZ4 Recovery 单成员 TAR。结果在源码根目录 dist/gts7fewifi-crypto-<时间>/，包含镜像、TAR、SHA256SUMS 和验包报告。脚本没有刷写、挂载或格式化设备的命令。

如果只想手工编译原始 recovery.img：

```bash
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_gts7fewifi-eng
m -j4 recoveryimage
```

原始结果在 out/target/product/gts7fewifi/recovery.img，后续可再次运行完整脚本增量编译并验包。不要执行旧的外部 setup.py，它不属于本包，可能把设备树覆盖成早期版本。

## 5. 配置要点与限制

- TW_INCLUDE_CRYPTO := true；本次分支据此启用 FBE、metadata 和 libresetprop 支持，不靠新增 UI 假装解密。
- linkblobs.sh 使用指定 ROM 的真实文件路径，不再解析 bootloader 第十个字符来猜库版本；这些库不是用户个人密钥。
- 两份第一阶段 modules.load 保持为空，触摸模块交给 TWRP 在后续阶段按 modules.dep 加载；不要重新填回第一阶段列表。
- 保留 kernel/DTB/DTBO 与触摸固件，Header v2 和 Recovery DTBO 参数由 mkbootimg.mk 处理。
- 保留 Data 的 FBE/metadata 配置，不删除锁屏文件、关闭加密或格式化。SELinux/硬件服务/凭据格式仍需实机排错。
- 本树也保留了若干上游分区配置，但仅 recoveryimage 经核查；不要据此构建并刷入 boot、vendor_boot、system 或 super。特别是此树的历史 super/vendor_boot 容量配置未作为本次 Recovery 验收目标，不可拿来给其他镜像定尺寸。
- 使用公开 AOSP 测试 AVB 密钥（见 BoardConfig），签名校验通过不等于三星设备信任该密钥。刷入必须满足设备自身解锁条件并由用户自行确认。
- 镜像不包含 userdata 不等于承诺任意设备状态下已有加密数据都可读取；备份个人数据，解密失败时先取日志，不要格式化。

## 6. 可复现性与排错

tools/t733-build-sources.txt 保留此前核心工程的版本记录，BUILD-REFERENCE.json 记录本次验收二进制哈希和资产来源。它不是整个 Android 工程的锁定 manifest；同步分支可能前进，不能保证每次构建逐字节相同。需要严格复现时，应由构建者在已验证的完整 checkout 执行：

```bash
repo manifest -r -o manifest-pinned.xml
```

发布时同时保存锁定 manifest、设备树提交和编译日志。本包不包含完整 TWRP 平台源码或 kernel 源码，而是使用提取的 kernel prebuilt。

编译失败贴最后报错，保留源码和 out 缓存；不要首先 clean 全树。源码实现与核查脚本不符时应核对版本，不要删掉保护检查。修改库、模块或 firmware 后，需要同步更新 tools/crypto-profile-sha256.json 及模块清单，并重新验证；本包的固定哈希检查仅适用于这个预编译 profile。

实机测试顺序：Recovery 启动 → 触摸 → PIN 页面 → 解锁 Data → 确认内部存储能读取。跳过或取消解密后能进入主界面不能算解密成功。V2 参考包的启动和 Data 解密由用户手动确认；脚本本身不执行设备测试。

## V2 启动修复

V1 混入了较新 LineageOS 的通用 C++/Keymaster 支持库，引用旧 TWRP 平台没有的 __libcpp_verbose_abort、OPENSSL_sk_* 等符号。实机卡在等待 Keymaster/Keystore2。V2 保留四份必要的 ROM 硬件库，恢复匹配基础库，并删除九份 vendor 覆盖文件；不要将那批基础库重新复制回来。验包现在增加关键服务的 ELF 强符号闭合检查，它仍不能代替实际 linker namespace 和服务运行验证。

参考 V2 是在 EXPERIMENTAL-1 编译结果上修补 ramdisk，因此版本页可能仍显示 EXPERIMENTAL-1；/t733-build-id 可区分 V2。构建参数保持该基线，不通过改版号冒充重新测试。
