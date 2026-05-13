from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI


class DistributedTreeAI(DistributedNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory("DistributedTreeAI")
