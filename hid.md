## Usage Types
### Controls
+ LC: Linear Control
+ OOC: On/Off Control
+ MC: Momentary Control
+ OSC: One Shot Control
+ RTC: Re-trigger Control
### Data
+ Sel: Selector
+ SV: Static Value
+ SF: Static Flag
+ DV: Dynamic Value
+ DF: Dynamic Flag
### Collection
+ NAry: Named Array
+ CA: Application Collection
+ CL: Logical Collection
+ CP: Physical Collection
+ US: Usage Switch
+ UM: Usage Modifier

## Report Description
单个数据包长51字节
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
