from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedSmoothNodeAI import DistributedSmoothNodeAI


class DistributedPlayerAI(DistributedSmoothNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedPlayerAI")

    def __init__(self, air):
        DistributedSmoothNodeAI.__init__(self, air)

        self.name = ""

    def setName(self, name):
        self.name = name

    def d_setName(self, name):
        self.sendUpdate("setName", [name])

    def b_setName(self, name):
        self.setName(name)
        self.d_setName(name)

    def getName(self):
        return self.name
