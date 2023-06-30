from typing import NamedTuple, TypeVar, Generic, Self
import bisect
from abc import ABCMeta, abstractmethod

from easing import EasingFunction, LMOST


# 泛型约束：可以插值（跟自己相加减，跟浮点数相乘除可以得到同类型结果）
class Interpable(metaclass=ABCMeta):
    @abstractmethod
    def __add__(self, other: Self) -> Self:
        pass

    @abstractmethod
    def __sub__(self, other: Self) -> Self:
        pass

    @abstractmethod
    def __mul__(self, other: float | int) -> Self:
        pass


T = TypeVar('T', bound=Interpable)


class Joint(NamedTuple, Generic[T]):
    timestamp: float
    value: T
    easing: EasingFunction


class Bamboo(Generic[T]):
    joints: list[Joint[T]]

    def __init__(self) -> None:
        self.joints = []

    def cut(self, timestamp: float, value: T, easing: EasingFunction | None = None) -> None:
        easing = easing or (lambda _: 0)
        bisect.insort_left(self.joints, Joint(timestamp, value, easing), key=lambda j: j.timestamp)

    def embed(self, start: float, end: float, start_value: T, end_value: T, easing: EasingFunction) -> None:
        assert start < end
        left = Joint(start, start_value, easing)
        insert_point = bisect.bisect_left(self.joints, start, key=lambda j: j.timestamp)
        assert insert_point == bisect.bisect_left(self.joints, end, key=lambda j: j.timestamp)
        if insert_point == 0:
            self.joints.insert(0, Joint(end, end_value, LMOST))
            self.joints.insert(0, left)
            return
        left_easing = self.joints[insert_point - 1].easing
        self.joints.insert(insert_point, Joint(end, end_value, left_easing))
        self.joints.insert(insert_point, left)

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
            return f'''Bamboo(min={self.joints[0].timestamp}, max={self.joints[1].timestamp}, total_joints={len(self.joints)})'''
        return 'Bamboo(empty)'
