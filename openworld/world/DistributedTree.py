from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNode import DistributedNode


class DistributedTree(DistributedNode):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedTree")

    def announceGenerate(self):
        DistributedNode.announceGenerate(self)

        marker = loader.loadModel("models/misc/smiley")
        marker.reparentTo(self)
        marker.setPos(*self.getPos())
        marker.setScale(1)

        self.reparentTo(render)
