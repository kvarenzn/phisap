<div align="center">
<h1 align="center">phisap</h1>

PHIgros Semi-Automatic Player

适用于音游Phigros的半自动打歌器，仅支持安卓设备

![最高支持](https://img.shields.io/badge/最高支持-Phigros%203.1.0-blue.svg)

</div>


## 目录
* [免责声明](#免责声明)
* [灵感来源](#灵感来源)
* [成果展示](#成果展示)
* [如何使用](#如何使用)
  * [准备](#准备)
  * [运行](#运行)
* [工作原理](#工作原理)
* [注意事项](#注意事项)
* [暂不支持的谱面](#暂不支持的谱面)
* [课题模式](#课题模式)
* [遇到问题?](#遇到问题?)
* [对Arcaea的支持](#对arcaea的支持)
* [致谢](#致谢)
* [开源许可](#开源许可)
* [更新日志](#更新日志)

## 免责声明
+ 本项目属于个人兴趣项目，与厦门鸽游网络有限公司无关。
+ **本项目内不含任何版权素材，且本项目并非商业项目**。
+ 项目的服务端借用自[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)，在此感谢scrcpy的作者和维护者们。
+ 截止目前，项目作者从未在任何除GitHub以外的平台上以任何方式宣传过本项目。

## 灵感来源
> Tip: sudo 板子自己打歌

## 成果展示

<details>
<summary>两张手机截图</summary>

![AT Complete](./screenshots/phone-shot1.jpg)

![IN Complete](./screenshots/phone-shot2.jpg)

</details>

## 如何使用

### 准备
0. **请安装Python 3.11**
    + 请使用正式版，不要使用开发者预览(early developer preview)版
        + 如果你非要用，请使用`3.11.0a5`及以后的版本，否则你可能会遇到一些问题，见issue#71
1. 使用`pip install -r requirements.txt`安装依赖
2. 请安装`Android Debug Bridge`，**要求版本号至少为`1.0.41`**，并确保相应的环境变量已经配置好。
3. 请准备Phigros的游戏安装包/通用数据包。目前支持的游戏版本为2.0.0至3.1.0
    + 如果你的phigros是taptap版，那么只需要游戏安装包即可
        + 如果你使用*nix系统(如Linux或Mac OS)，则你可以使用如下的`bash shell`命令从安卓设备上提取安装包
            ```bash
            adb pull $(adb shell pm path com.PigeonGames.Phigros | cut -f2 -d:) ./Phigros.apk
            ```
        + 如果你使用Windows操作系统，那么你可以在`powershell`中运行下面的命令
            ```powershell
            adb pull (adb shell pm path com.PigeonGames.Phigros).Split(":")[1] ./Phigros.apk
            ```
    + 如果你的phigros是Google Play版，那么**不要提取安装包，请提取数据包**(后缀为.obb)，因为谱面数据并不在安装包内
        + 这个数据包一般在游戏设备的`/sdcard/Android/obb/com.PigeonGames.Phigros/`目录下
        + 名称类似于`main.82.com.PigeonGames.Phigros.obb`
        + 大小约为1.3GB
        + 使用`adb pull`或者文件管理器直接复制出来即可
    + 当然，如果你不想手动提取，也可以直接去网上下载一个phigros的安装包或数据包，注意版本对应即可
4. 准备服务端。请去[scrcpy的releases页面](https://github.com/Genymobile/scrcpy/releases) 下载`scrcpy-server-v2.0`，不要下载成别的版本。下载完成后，请将文件直接放置在phisap的根目录（与`main.py`之类的文件在同一文件夹即可），不要更改文件的名称（比如添加后缀），否则phisap将无法识别。
    + 如果你使用*nix系统，且安装有wget，那么下面的命令与上面描述的操作等效:
        ```bash
        cd phisap  # 定位到phisap的根目录下
        wget https://github.com/Genymobile/scrcpy/releases/download/v2.0/scrcpy-server-v2.0
        ```

### 运行
```bash
cd phisap # 将CWD(Current Working Directory，当前工作目录)设置为phisap的根目录，以便phisap查找服务端文件
python main.py
```

## 工作原理
+ 读取并缓存游戏安装包中的所有谱面文件
+ 解析谱面文件，分析出每个音符的击打位置、击打方式和击打时间
+ 将这些击打操作转换为触控事件序列
    + 即按下(DOWN)、移动(MOVE)和抬起(UP)
+ 开始操作后，逐一向设备发送这些触控事件


## 注意事项
+ 虽然phisap的灵感来源为`sudo 板子自己打歌 `，不过**本程序并不依赖root权限工作**
+ 一些情况下有可能因误触发三指截屏或通知中心而导致miss，不是每台设备都会触发，视厂商和设备型号而定
+ **phisap当前完美支持的最高版本为3.1.0**，所有的曲目/任意难度均可以打出金φ，除了一些特殊类型的谱面（不用担心，不会影响rks）。这些谱面详见[暂不支持的谱面](#暂不支持的谱面)。不过，在使用phisap时可能会发现一些谱面无法AP，那么这时你需要
    + 确保计时器同步的精确程度满足要求，如果你发现phisap打出了FULL COMBO，但并没有AP，这**一定**说明你的计时器同步没有做好
    + 如果计时器同步没有问题，那么你可以试试换一个规划算法。目前一些谱面只能由algo1达成AP，而另一些只能由algo2达成，当然，大部分的谱面使用algo1和algo2都可以完成
    + 如果你发现还是不行，那么你可以考虑开一个issue，跟我说明这个问题

PS: 如果你知道怎样实现不root的前提下精确获知当前曲目进度，且愿意帮助本项目的话，请开issue告知我做法

## 暂不支持的谱面

### 单曲精选集中的《Random》

暂时没有找到什么可以自动化判断当前谱面的办法，如果你有好的想法，请开issue。或许图像识别是一个可行的方式

不过目前phisap可以解包出全部的随机谱面（ID为`Random.SobremSilentroom.<n>`，`<n>`从0到6），所以理论上，如果你的手速够快，完全可以应对随机谱面

### 愚人节谱

这些玩意太逆天了，不在phisap的全p目标范围内。phisap作者并不会针对愚人节谱面进行规划算法的改进

## 课题模式
phisap并没有对课题模式做特殊的支持，将来也许会有

不过现有的功能完全可以使你拿到彩48标签，但是需要一点点技巧

我推荐的配置是
+ 迷宫莉莉丝 (AT16)
+ 狂喜兰舞 (AT16)
+ DESTRUCTION 3,2,1 (AT16)

也就是下面这三个，顺序任意
![推荐彩48配置](./screenshots/phone-shot3.jpg)
这三个谱面的特点是开局没有过分的判定线演出，便于手动同步定时器，同时相比于其他AT16，这三个谱面在课题模式下也算是判定比较宽松的

然后按照如下步骤操作phisap
1. 使用algo1规划这三个谱面（注意难度选AT）
    + 计时器同步方式选手动同步，选定曲目ID和难度之后点开始，按钮变成“开始操作”后关掉phisap，再打开，重复这一步骤
        + 这个操作逻辑确实有点蠢，不过新UI正在设计了（
2. 同步方式选手动，曲目ID选择第一首的，难度选AT，规划算法选不规划，然后点开始
3. 在游戏设备上设置课题模式并开始
4. 看着游戏设备，在note快落到判定线时点击“开始操作”按钮或者按下空格键
5. 观察note被击打时相对判定线的位置，调整“微调”，确保note在击打时跟判定线重合
    + 如果你开局就蓝线了那也就甭微调了，直接重开罢
6. 在phisap自动游玩当前谱面时，调整曲目ID为下一首的曲目ID
7. 在phisap的按钮重新变回“开始”/看到控制台输出“操作结束”后，点击“开始”按钮。此时你的游戏设备应该还在加载下一首曲目
8. 为剩下两首曲目重复步骤4到7
9. 如果运气好的话，你应该能得到一个彩48

## 遇到问题?
**请开issue，并在issue中包含如下内容**
+ 你的操作系统版本
+ 你遇到的问题
+ 能反映遇到的问题的日志、记录或者截图

**如果之后的更新解决了你的问题，请关闭自己开的issue**

**如果一百度就能找到解决方法的问题，不要开issue，例如依赖安装问题，如果你开了也会被我关上甚至删除**

## 对Arcaea的支持
项目`闊靛緥婧愮偣/`文件夹下的文件实现了最简陋的对音游韵律源点（arcaea）的支持，原理完全相同。

需要您手动提取谱面文件（比phigros简单，网上搜索一下就能找到），再运行`闊靛緥婧愮偣/main.py`，按照程序提示输入。

支持的谱面声明包括：
+ 函数：`arc()`、`arctap()`、`timing()`和`hold()`，`scenecontrol()`会被忽略
+ easing：`b`、`s`、`si`、`so`、`sisi`、`soso`、`siso`和`sosi`
+ 其余**均不支持**，尤其是对camera的操作

## 致谢
+ `control.py`中的大部分代码参考自[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy) 。
+ `catalog.py`和`extract.py`中的代码参考自[Perfare/AssetStudio](https://github.com/Perfare/AssetStudio) 。

感谢上述优秀的项目和创造或维护它们的个人或企业。

## 开源许可
除部分有参考来源的代码按其作者要求的方式开源外，**其余代码按照`WTFPL`许可开源。**

预告：将来可能会有一个大更新，其特征为更换现有的UI库`tkinter`为其他库，届时将变更开源许可为`GPLv3`。如果你有`GPL`协议洁癖，请做好心理准备

## 更新日志
### (2023/07/02) v0.4
#### 算法
+ 为了支持其他格式的谱面，现在不再假设屏幕尺寸为一个固定的值，默认pec格式为2048x1400，phigros格式为16x9(旧谱(`formatVersion = 1`)为880x520)
+ 初步支持pec格式和phigros格式(json)的自制谱的加载

#### 界面
+ 为了支持自制谱的加载，对UI进行了较大幅度的改动
    + 但并没有微调布局，所以强迫症应该受不了

### (2023/07/01) v0.3
#### 算法
+ 音符x轴偏移量(`position_x`)乘的系数由原来的`72`变更为`1`
+ 规划算法默认的屏幕尺寸由1280x720变更为16x9
+ 所有的二维向量/坐标运算现由python内建的复数运算驱动
    + 规划算法的运行效率将会有明显的提升
+ 以上更改是为了适配其他谱面格式(如PEC)做准备
+ 尚未完全确认这些变更带来的后果，如果有因为这次改动导致的无法AP，请开issue
#### 界面
+ 现在，GUI窗口的标题栏中会显示phisap的版本

### (2023/06/29) v0.2
+ 重新依赖lz4.block用作解压缩lzma数据
    + 由于在Windows上，安装lz4需要依赖MSVC，因此可能一部分人会安装失败，此时phisap将启用纯python的解压函数实现

### (2023/06/28) v0.1
+ 为phisap加入版本号，并设定初始版本号为0.1
+ 在README中加入更新日志
+ 修复此前遇到的一些问题
