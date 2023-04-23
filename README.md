# phisap - PHIgros Semi-Auto Player
适用于音游Phigros的半自动打歌器，**仅支持安卓设备**

PS: 如果你知道如何实现iOS设备的无越狱远程控制（发送触控事件），且愿意帮助本项目的话，请开issue告诉我如何做，我会在之后加上对iOS设备的支持

## 免责声明
+ 本项目属于个人兴趣项目，与厦门鸽游网络有限公司无关。
+ **本项目内不含任何版权素材，且本项目并非商业项目**。
+ 项目的服务端借用自[Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)，在此感谢scrcpy的作者和维护者们。
+ 截止目前，项目作者从未在任何除GitHub以外的平台上以任何方式宣传过本项目。

## 灵感来源
> tips: sudo 板子自己打歌

## 成果展示

<details>
<summary>三张手机截图</summary>

![截图1](./screenshots/phone-shot1.jpg)

![截图2](./screenshots/phone-shot2.jpg)

![截图3](./screenshots/phone-shot3.jpg)

</details>

## 如何使用

### 准备
0. **请安装Python 3.10**
    
    + 注意：Python 3.11目前会有安装依赖方面的问题，所以请不要使用Python 3.11来运行phisap
1. 使用`pip install -r requirements.txt`安装依赖
2. 请安装`Android Debug Bridge`，**要求版本号至少为`1.0.41`**，并确保相应的环境变量已经配置好。
3. 请准备Phigros的游戏安装包。目前支持的游戏版本为2.0.0至3.0.0
	+ 可以使用如下命令从安卓设备上提取安装包
		```bash
		adb pull $(adb shell pm path com.PigeonGames.Phigros | cut -f2 -d:) ./Phigros.apk
		```
4. 准备服务端。请去[scrcpy的releases页面](https://github.com/Genymobile/scrcpy/releases) 下载`scrcpy-server-v2.0`，不要下载成别的版本。下载完成后，请将文件直接放置在phisap的根目录（与`main.py`之类的文件在同一文件夹即可），不要更改文件的名称（比如添加后缀），否则phisap将无法识别。
    + 如果你使用*nix系统，且安装有wget，那么下面的命令与上面描述的操作等效:
        ```bash
        cd phisap  # 定位到phisap的根目录下
        wget https://github.com/Genymobile/scrcpy/releases/download/v1.25/scrcpy-server-v2.0
        ```

### 运行
```bash
python main.py
```

## 注意事项
+ 虽然phisap的灵感来源为`sudo 板子自己打歌 `，不过**本程序并不依赖root权限工作**
+ 本程序的工作原理为向游戏设备发送触控事件来模拟人类游玩时的点击、长按或滑动，所以一些情况下仍有可能因误触发三指截屏或通知中心而导致miss
+ **phisap当前完美支持的最高版本为2.1.1**，也就是说2.1.1及以前的版本所有曲目都可以打出金phi（但需要精确调整偏移）。之后的版本部分谱面会有问题，详见[暂不支持的谱面](#暂不支持的谱面)

PS: 如果你知道怎样实现不root的前提下精确获知当前曲目进度，且愿意帮助本项目的话，请开issue告知我做法

## 暂不支持的谱面
### 普通谱面

<details>
<summary>点击展开</summary>

下面这些谱面由于phisap目前的规划算法限制暂时无法被打出Phi（大部分是由于Flick判定失效，所以说啊...）

这些问题将在phisap后续的更新中被修复

注：这些谱面将按照章节列出。如果一个章节名用_斜体_表示，意味着这个章节的曲目暂时没有测试完全，也就是说**这个章节的记录并不完整**。如果你发现了**该章节中**无法被phisap打出Phi的曲目，且这里没有列出，请开issue。如果可能的话最好在issue中描述一下大致是在哪里出现的Good/Bad/Miss，便于修复该问题。

#### _Single_

| 曲目        | 难度 | 最佳成绩 |
| ----------- | ---- | -------- |
| Snow Desert | IN   | 1 miss   |

#### Legacy

全φ

#### Chapter 5

全φ

#### Chapter 6

全φ

#### Chapter 7

全φ

#### _Chapter 8_

#### Side story 1

全φ

#### Side story 2

| 曲目                       | 难度 | 最佳成绩           |
| -------------------------- | ---- | ------------------ |
| INFiNiTE ENERZY -Overdoze- | AT   | 1 miss (使用algo2) |

#### _茶鸣拾贰律_

#### 姜米條

全φ

#### Lanota

| 曲目                  | 难度 | 最佳成绩 |
| --------------------- | ---- | -------- |
| Protoflicker          | IN   | 1 miss   |
| You are the Miserable | AT   | 1 miss   |

#### Kalpa

全φ

#### Muse Dash

全φ

#### WAVEAT

全φ

#### GOOD

全φ

#### HyuN

全φ

#### Rising Sun Traxx

全φ

</details>

### 单曲精选集中的《Random》

暂时没有找到什么可以自动化判断当前谱面的办法，如果你有好的想法，请开issue。或许图像识别是一个可行的方式

不过目前phisap可以解包出全部的随机谱面（ID为`Random.SobremSilentroom.<n>`，`<n>`从0到6），所以理论上，如果你的手速够快，完全可以应对随机谱面

### 愚人节谱

这些玩意太逆天了，不在phisap的全p目标范围内。phisap作者并不会针对愚人节谱面进行规划算法的改进


## 如果你在使用过程中遇到了问题，请开issue
**请在issue中包含如下内容**
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
