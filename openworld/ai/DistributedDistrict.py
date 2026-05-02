from direct.distributed.DistributedObject import DistributedObject


class DistributedDistrict(DistributedObject):

    def announceGenerate(self):
        DistributedObject.announceGenerate(self)

        self.sendUpdate("requestJoin", [])
