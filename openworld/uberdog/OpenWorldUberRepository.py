from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectUD import DistributedObjectUD

from ardos.ArdosInternalRepository import ArdosInternalRepository
from openworld.distributed import OpenWorldGlobals


class OpenWorldUberRepository(ArdosInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory("OpenWorldUberRepository")
    notify.setInfo(True)

    GameGlobalsId = OpenWorldGlobals.ROOT_DO_ID

    def __init__(self, baseChannel, stateServerChannel):
        ArdosInternalRepository.__init__(
            self, baseChannel, serverId=stateServerChannel, dcSuffix="UD"
        )

        self.authMgr = None

    def handleConnected(self):
        ArdosInternalRepository.handleConnected(self)

        # Tell Ardos who we are.
        # Helpful for debugging/logs.
        self.setConName("OpenWorldUD")

        # Root parent for all distributed objects.
        # This is the start of the network tree.
        rootObj = DistributedObjectUD(self)
        rootObj.generateWithRequiredAndId(self.getGameDoId(), 0, 0)

        self.createGlobals()

        self.notify.info("Online!")

    def createGlobals(self):
        """
        Create "global" objects.
        It's helpful to think of these as networked singletons.
        :return:
        """
        self.authMgr = self.generateGlobalObject(
            OpenWorldGlobals.AUTH_MGR_DO_ID, "AuthMgr"
        )
