from direct.distributed.DistributedObjectUD import DistributedObjectUD


class DistributedPlayerUD(DistributedObjectUD):

    def __init__(self, air):
        DistributedObjectUD.__init__(self, air)

        self.name = ""

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name
