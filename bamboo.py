from typing import NamedTuple, TypeVar, Generic, Protocol, runtime_checkable
import bisect

from easing import EasingFunction, LVALUE


# 泛型约束：可以插值（跟自己相加减，跟浮点数相乘除可以得到同类型结果）

S = TypeVar('S', bound='_Interpable')


@runtime_checkable
class _Interpable(Protocol):
    def __add__(self: S, other: S, /) -> S:
        ...

    def __sub__(self: S, other: S, /) -> S:
        ...

    def __mul__(self: S, other: float | int, /) -> S:
        ...


T = TypeVar('T', bound=_Interpable)


class Joint(NamedTuple, Generic[T]):
    timestamp: float
    value: T
    easing: EasingFunction


class Bamboo(Generic[T]):
    joints: list[Joint[T]]

    def __init__(self) -> None:
        self.joints = []

    def cut(self, timestamp: float, value: T, easing: EasingFunction | None = None) -> None:
        easing = easing or LVALUE
        bisect.insort_left(self.joints, Joint(timestamp, value, easing), key=lambda j: j.timestamp)

    def embed(self, start: float, end: float, start_value: T, end_value: T, easing: EasingFunction) -> None:
        assert start < end
        insert_point = bisect.bisect_left(self.joints, start, key=lambda j: j.timestamp)
        if insert_point < len(self.joints) and self.joints[insert_point].timestamp == start:
            # 更新起点记录，插入终点记录
            left_easing = self.joints[insert_point].easing
            self.joints[insert_point] = self.joints[insert_point]._replace(easing=easing)
            assert insert_point >= len(self.joints) - 1 or self.joints[insert_point + 1].timestamp >= end
            if insert_point >= len(self.joints) - 1 or self.joints[insert_point + 1].timestamp > end:
                self.joints.insert(insert_point + 1, Joint(end, end_value, left_easing))
        elif insert_point == len(self.joints):
            # 在尾部插入起点记录和终点记录
            self.joints.append(Joint(start, start_value, easing))
            self.joints.append(Joint(end, end_value, self.joints[-2].easing))
        else:
            # 在中间插入起点记录，视情况更新现有终点记录/插入终点记录
            assert self.joints[insert_point].timestamp >= end
            if self.joints[insert_point].timestamp == end:
                self.joints[insert_point] = self.joints[insert_point]._replace(value=end_value)
                self.joints.insert(insert_point, Joint(start, start_value, easing))
            else:
                left_easing = self.joints[insert_point - 1].easing
                self.joints.insert(insert_point, Joint(end, end_value, left_easing))
                self.joints.insert(insert_point, Joint(start, start_value, easing))

    def __getitem__(self, time: float) -> T:
        right = bisect.bisect_left(self.joints, time, key=lambda j: j.timestamp)
        left = right - 1
        if right == len(self.joints):
            return self.joints[left].value
        if self.joints[right].timestamp == time or right == 0:
            return self.joints[right].value
        start = self.joints[left]
        end = self.joints[right]
        t = start.easing((time - start.timestamp) / (end.timestamp - start.timestamp))
        return start.value + (end.value - start.value) * t

    def __repr__(self) -> str:
        if self.joints:
            return f'''Bamboo(min={self.joints[0].timestamp}, max={self.joints[-1].timestamp}, total_joints={len(self.joints)})'''
        return 'Bamboo(empty)'
