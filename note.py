class Note:
    typ: int
    time: int
    x: float
    hold: float
    speed: float
    floor: float

    TAP: int = 1
    DRAG: int = 2
    HOLD: int = 3
    FLICK: int = 4

    def __init__(self, typ: int, time: int, x: float, hold: float, speed: float, floor: float):
        self.typ = typ
        self.time = time
        self.x = x
        self.hold = hold
        self.speed = speed
        self.floor = floor

    @classmethod
    def from_dict(cls, d: dict):
        return cls(d['type'], d['time'], d['positionX'], d['holdTime'], d['speed'], d['floorPosition'])

    def __repr__(self):
        return (f'''Note({['TAP', 'DRAG', 'HOLD', 'FLICK'][self.typ - 1]}, time={self.time}, x={self.x}, '''
                f'''hold={self.hold}, speed={self.speed}, floor={self.floor})''')

