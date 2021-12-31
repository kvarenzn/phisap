# phisap - PHIgros Semi-Auto Player
适用于音游Phigros的半自动打歌器，**仅支持安卓/鸿蒙设备**。

## 免责声明
**本项目属于个人兴趣项目，与厦门鸽游网络公司无关。**\
**您因使用或修改本程序所造成的一切后果由您自己承担。**\
包括但不限于：失去游玩的乐趣、被其他人辱骂或被官方删除在线存档或帐号等。因此，请酌情使用。

## 灵感来源
> tips: sudo 板子自己打歌

## 成果展示（雾）

![截图1](./screenshots/phone-shot1.jpg)

![截图2](./screenshots/phone-shot2.jpg)

![截图3](./screenshots/phone-shot3.jpg)

## 如何使用

### 准备
0. **请安装Python 3.10。**
1. 请安装`requirements.txt`中的全部依赖（使用`pip install -r requirements.txt`）。
2. 请确保`adb`命令在`PATH`变量中。如果没有请下载安装并配置`PATH`变量。
3. 请准备Phigros的安装包，目前支持v1.6.9至v2.0.1。如果您的安卓/鸿蒙设备中已经安装有Phigros,则可以依照下面的方法提取：
   1. 将设备连接到安装有`adb`的计算机，且确保设备已开启USB调试模式，且已授权计算机进行调试。
   2. 在计算机上执行命令`adb shell pm path com.PigeonGames.Phigros`，该命令会打印出安装包的路径。
   3. 记上一步得到的路径为`<pkgpath>`(`package:`之后的内容)，执行命令`adb pull <pkgpath> <storage path>`。则安装包将保存到`<storage path>`下（`<storage path>`由您自己指定）。
4. 准备服务端。以下操作二选一。
   1. 如果您的游戏设备为`aarch64`架构，那么可以尝试从[releases](https://github.com/kvarenzn/phisap/releases/) 下载预编译的服务端，并放置在`server/`下。
   2. 如果不是，请按照如下步骤自行编译
      1. **请确保Android NDK已经安装并正确配置**，下一步需要依赖这一步的配置。至于如何配置请参考百度或谷歌。
      2. 编译服务端：请选择下面两项中的一项执行
         1. 如果您的计算机中有`make`命令，请`cd server/`，之后再`make build install`。
         2. 否则，请
            1. 使用`Android Studio`打开`server/`并编译，或者`cd server/`之后`./gradlew -p . assembleRelease`。
            2. 找到编译出的apk文件，一般在`server/build/outputs/apk/release/server-release-unsigned.apk`，请手动将它移动到`server/`并重命名为`phisap-server`。

### 运行
```bash
python main.py
```

### 运行截图
![截图1](./screenshots/shot1.png)

## 注意事项
+ 本程序不依赖root权限工作。
  + 一些设备可能会需要root权限来访问`/data/`，这会导致无法无root提取游戏安装包，这时请您自行百度或谷歌下载游戏安装包。
+ 本程序的工作原理为向游戏设备发送触控事件来模拟人类游玩时的点击、长按或滑动。所以，对于部分设备或部分情况，仍有可能因误触发三指截屏或通知中心而导致miss。
+ 本程序依赖使用者手动设置时延来同步游戏内计时器。这也是本程序称为“半自动”的原因。
+ 由于客观原因：
  + 某一时刻为某一曲目的某难度配置的时延并不能保证在下一次游玩相同曲目的相同难度时仍然有效。可能需要在前一时延上进行微调。目前尚未找到不使用root权限而与游戏内计时器同步的方法。
  + 在某些情况下（如游戏设备后台运行太多程序时），游戏内计时器的时间变化率可能与现实时间并不同步，这有时会导致曲目开始时先于判定时刻击打note，临近曲目结束时反而落后于判定时刻的情况，也有可能反过来。
  + 游戏有时会发生漏判现象。这会导致相同的触摸事件序列在应用于同一谱面时，所得分数并不相同。可能需要多尝试几次才能达到φ的成绩。


## 已知的BUG与临时修复方法
### 程序在部分旧版本的adb下会阻塞且没有任何额外输出
如[issue#8](https://github.com/kvarenzn/phisap/issues/8)

这是因为部分旧版本的adb不支持或部分支持`adb reverse`命令。在当前版本下，这个命令是用于服务端(于游戏设备)和客户端(于运行本程序的计算机)之间建立初步通信的重要命令。服务端和客户端之间无法建立通信，导致双方阻塞。本程序在之后的更新中可能会支持`adb forward`命令作为备选通信方案。

**要临时解决此问题，请使用最新版本的adb替换(不是共存安装)您当前使用的版本。**

如果不确定您当前使用的adb版本，请使用`adb version`命令查询。

## 对Arcaea的支持
项目`闊靛緥婧愮偣/`文件夹下的文件实现了最简陋的对音游韵律源点（arcaea）的支持，原理完全相同。

需要您手动提取谱面文件（比phigros简单，网上搜索一下就能找到），再运行`闊靛緥婧愮偣/main.py`，按照程序提示输入。

支持的谱面声明包括：
+ 函数：`arc()`、`arctap()`、`timing()`和`hold()`，`scenecontrol()`会被忽略
+ easing：`b`、`s`、`si`、`so`、`sisi`、`soso`、`siso`和`sosi`
+ 其余**均不支持**，尤其是对camera的操作

暂时不打算对arcaea进行更深入的支持，加入这些内容的原因是不想让这些以前写过的东西浪费掉，或许能作抛砖引玉之用。

## 致谢
+ `control.py`和`server/`中的大部分代码参考自[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) ，并使用`python`和`kotlin`语言重写。
+ `catalog.py`和`extract.py`中的代码参考自[Perfare/AssetStudio](https://github.com/Perfare/AssetStudio) ，并使用`python`语言重写。
+ 谱面解析算法参考自[0thElement/PhiCharter](https://github.com/0thElement/PhiCharter) 。

感谢上述优秀的项目和创造或维护它们的个人或企业。

## 开源许可
除部分有参考来源的代码按其作者要求的方式开源外，**其余代码按照`WTFPL`许可开源。**
