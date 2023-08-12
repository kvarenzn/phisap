# OTG/HID功能开发笔记
## 目标
我们的目标是要模拟出一个带有最多十点触控的触控屏(Touch Screen)，以作为现在正在使用的`scrcpy-server`的平替

## 什么是OTG
+ OTG即On-The-Go，具体定义请百度/谷歌/维基
+ 简单来说就是让安卓设备可以接入其他USB设备，以实现共同协作
+ 同时可以实现USB的主从关系反转，如果安卓设备接入计算机，则可以让安卓设备作为主机，计算机作为从机，从而实现我们需要的功能

## 什么是HID
+ HID即Human Interface Device，即人机交互设备，是一类设备的统称
+ 这类设备的特点是在绝大多数的系统上可以原生跨平台，即无需额外安装驱动（操作系统自带驱动）
+ HID包含很多类型的设备，如鼠标、键盘、手柄、触控笔，当然也包含Touch Screen

## Android开放配件 (Android Open Accessory, AOA)协议
+ 为了在安卓设备上支持更多外围配件，安卓制定了AOA协议
+ 该协议可以方便地在安卓设备上注册并使用HID，可以达到近乎原生的支持（其实就是原生）
+ 该协议有两个版本，AOAv1和AOAv2，v2兼容v1，但支持更多功能，包括HID。所以我们直接使用AOAv2协议

## 如何达成目的
+ 不借助adb，计算机借助USB协议直接与设备建立通信
+ 通信完成后，计算机通过AOAv2协议借助USB的control transfer向安卓设备发送注册HID的指令，假装自己是一个触控屏，准确来说是发送下面两个指令
    + `ACCESSORY_REGISTER_HID`: 注册一个新的HID设备，告知指代该设备的唯一ID
    + `ACCESSORY_SET_HID_REPORT_DESC`: 向安卓设备发送我们模拟出来的HID设备的Report Description（具体内容见Report Description一节），也就是告诉安卓系统，我们这个配件有什么功能，会发送什么样的数据，你收到数据后应该如何解析
+ 指令发送完毕后，我们稍微等待一段时间(几百毫秒左右)，确保设备注册完毕
+ 我们按照需求，和Report Description中指定的格式，向安卓设备循环发送触控信息
    + 通过`ACCESSORY_SEND_HID_EVENT`这个指令
+ 不需要设备连接了，我们发送`ACCESSORY_UNREGISTER_HID`指令，取消注册我们之前注册的设备（断开连接）

## Report Description
为了向系统描述我们的触控屏都有什么功能，我们需要手动设计并编写Report Description。
phisap项目中用到的Report Description如下
```
Usage Page (Digitalizers)
Usage (Touch Screen)
Collection (Application)
    Usage (Finger)
    Collection (Logical)
        Usage (Contact Identifier) ; 4 bits for pointer ID
        Report Size (4)
        Report Count (1)
        Logical Minimum (0)
        Logical Maximum (9)
        Input (Data, Variable, Absolute)
        Usage (Tip Switch) ; 1 bit for status (DOWN, UP)
        Logical Minimum (0)
        Logical Maximum (1)
        Report Size (1)
        Report Count (1)
        Input (Data, Variable, Absolute)
        Report Size (3) ; 3 bits for padding
        Report Count (1)
        Input (Constant)
        Usage Page (Generic Desktop Page)
        Usage (X) ; 16 bits for position x
        Usage (Y) ; 16 bits for position y
        Logical Minimum (0)
        Logical Maximum (65535)
        Report Size (16)
        Report Count (2)
        Input (Data, Variable, Absolute)
    End Collection
    ; (repeat 9 times)
    Usage Page (Digitalizers)
    Usage (Contact Count) ; 4 bits for current pointers count
    Logical Maximum (16)
    Report Size (4)
    Report Count (1)
    Input (Data, Variable, Absolute)
    Usage (Contact Count Maximum)
    Report Size (4) ; 4 bits for max pointers count (10)
    Report Count (1)
    Input (Constant)
End Collection
```

大意：
+ 这是一个Touch Screen
    + 每次汇报10个Finger的状态，每个Finger包含
        + `Contact Identifier`: Finger的编号，用于指定是哪根手指，4个bit，从0到9
        + `Tip Switch`: 表示当前某根手指是否按下
        + (3bit的Padding)
        + `X`: 手指的X坐标，其最大取值(`Logical Maximum`)表示屏幕的宽度，16个bit
        + `Y`: 手指的Y坐标，其最大取值(`Logical Maximum`)表示屏幕的高度，16个bit
    + 除此之外，额外汇报如下信息：
        + `Contact Count`: 表示当前屏幕上共有几个触点，4个bit
        + `Contact Count Maximum`: 表示屏幕最多支持几点触控，4个bit (这个应该不用汇报，因为屏幕默认最多支持10点触控)

那么根据Report Description中的信息，我们每次上报都需要传输51bytes的数据，假设我们每毫秒汇报一次状态，则
所需最大传输速率为`51bytes * 1000/s == 51KB/s`，应该远小于USB1.0的最大传输速率

## 参考文献及代码(项目)
1. [AOA2](https://source.android.google.cn/docs/core/interaction/accessories/aoa2)
2. [Device Class Definition for Human Interface Devices (HID)](https://www.usb.org/sites/default/files/hid1_11.pdf)
3. [HID Usage Tables](https://usb.org/sites/default/files/hut1_4.pdf)
4. Genymobile/scrcpy: `app/usb/`目录下的代码