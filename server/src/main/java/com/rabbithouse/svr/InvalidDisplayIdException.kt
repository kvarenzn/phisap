package com.rabbithouse.svr

class InvalidDisplayIdException(displayId: Int) : RuntimeException("There is no display having id $displayId")